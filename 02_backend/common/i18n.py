"""Presentation-only localization and bounded bilingual query normalization."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT/'shared/locales/zh.json').read_text())
FOLDED = {key.casefold(): value for key, value in CATALOG.items()}
PHRASES = re.compile(r'(?<![A-Za-z0-9_])(?:' + '|'.join(re.escape(k) for k in sorted(CATALOG, key=len, reverse=True)
                     if k and CATALOG[k] != k) + r')(?![A-Za-z0-9_])', re.IGNORECASE)
PROTECTED = re.compile(r'https?://[^\s<>]+|\b[A-Z][A-Z0-9]*(?:[-:@][A-Za-z0-9_.:@/-]+)+\b|\b[a-f0-9]{32,64}\b|\b[a-z][a-z0-9]*(?:-[a-z0-9]+){2,}\b')
TEMPLATES = json.loads((ROOT/'shared/locales/patterns.json').read_text())

def compile_template(template):
    pieces = re.split(r'(\{\d+\})',template)
    expression = ''.join((r'(\d+)' if i == 1 and not pieces[0] else r'([^\n]+?)')
                         if re.fullmatch(r'\{\d+\}',part) else re.escape(part)
                         for i,part in enumerate(pieces))
    return re.compile(r'(?<![A-Za-z0-9_])'+expression+r'(?=$|[\s,;])')

PATTERNS = [(re.compile(source,re.I),target) for source,target in json.loads((ROOT/'shared/locales/claims.json').read_text())] + [(compile_template(source),target) for source,target in TEMPLATES]
DISPLAY_FIELDS = {'name','title','text','caption','caption_text','description','rationale','corrective_action',
                  'change','origin','source','provenance','rule','principle','definition','boundary',
                  'unit_constraints','label','detail','message','limitations','note','answer','findings',
                  'narrative','summary','missing_source','section','support','license','reason','question',
                  'source_text','excerpt','source_applicability','target_applicability','constraints','definitions','query_note','source_note','meaning'}


@lru_cache(maxsize=4096)
def translate_text(text, language='zh'):
    if language != 'zh' or not isinstance(text, str) or not text:
        return text
    if text in CATALOG:
        return CATALOG[text]
    stripped = text.strip()
    if stripped in CATALOG:
        return text.replace(stripped, CATALOG[stripped], 1)
    # Translate whole claims before individual terms. Captures preserve exact
    # identifiers and measurements; recursive translation handles nested labels.
    for pattern, target in PATTERNS:
        def render(match):
            return re.sub(r'\{(\d+)\}', lambda slot: translate_text(match.group(int(slot.group(1))+1)), target)
        text = pattern.sub(render,text)
    protected = []
    def protect(match):
        protected.append(match.group())
        return f'\ue000{len(protected)-1}\ue001'
    value = PROTECTED.sub(protect, text)
    value = PHRASES.sub(lambda match: FOLDED.get(match.group().casefold(),match.group()), value)
    return re.sub(r'\ue000(\d+)\ue001', lambda m: protected[int(m.group(1))], value)


def localize_payload(value, language, field=''):
    if language != 'zh':
        return value
    if isinstance(value, dict):
        result = {key: localize_payload(item,language,key if field not in {'definitions'} else field)
                  for key,item in value.items()}
        originals = {key:item for key,item in value.items() if (isinstance(item,str) or isinstance(item,list) and all(isinstance(part,str) for part in item)) and result.get(key)!=item}
        if originals:
            result['_source_texts'] = originals
        # The answer digest describes the displayed answer. Source/evidence
        # digests still identify the immutable canonical source material.
        if 'answer_sha256' in result and isinstance(result.get('answer'),str):
            result.setdefault('_source_texts',{})['answer_sha256'] = value['answer_sha256']
            result['answer_sha256'] = hashlib.sha256(result['answer'].encode()).hexdigest()
        return result
    if isinstance(value, list):
        return [localize_payload(item,language,field) for item in value]
    return translate_text(value,language) if field in DISPLAY_FIELDS and isinstance(value,str) else value


def request_language(scope, text=''):
    params = parse_qs(scope.get('query_string',b'').decode('utf-8',errors='replace'))
    explicit = params.get('lang',params.get('language',[]))
    headers = {key.lower():value for key,value in scope.get('headers',[])}
    requested = explicit[0] if explicit else headers.get(b'accept-language',b'').decode('ascii',errors='ignore')
    if requested:
        return 'zh' if requested.lower().startswith('zh') else 'en'
    return 'zh' if re.search(r'[\u3400-\u9fff]',text) else 'en'


QUERY_TERMS = {
    '热失控蔓延':'thermal propagation', '热失控':'thermal runaway', '热隔离':'thermal containment',
    '隔热屏障':'thermal barrier', '热管理':'thermal', '热风险':'thermal risk', '热余量':'thermal margin',
    '热响应':'thermal response', '电池包':'battery pack', '电池':'battery', '电芯':'cell',
    '能量密度':'energy density', '续航':'range', '安全':'safety', '成本':'cost', '重量':'mass',
    '质量':'mass', '温度':'temperature', '封装':'packaging', '外壳':'enclosure', '泄压':'venting',
    '气体':'gas', '标准':'standard', '合规':'compliance', '需求':'requirement', '设计':'design',
    '物料':'bom', '测试':'test', '验证':'validation', '临界':'MARGINAL', '不通过':'FAIL',
    '通过':'PASS', '图像':'image', '照片':'photograph', '文档':'document', '证据':'evidence',
    '阿特拉斯':'Atlas', '猎户座':'Orion', '织女星':'Vega', '宝马':'BMW',
}


def normalize_query(query):
    if not re.search(r'[\u3400-\u9fff]',query):
        return query
    reverse = {value:key for key,value in CATALOG.items() if value != key}
    if query.strip() in reverse:
        return reverse[query.strip()]
    value = query
    matched = False
    for term in sorted(QUERY_TERMS,key=len,reverse=True):
        if term in value:
            value = value.replace(term,' '+QUERY_TERMS[term]+' ')
            matched = True
    if not matched:
        return query
    return ' '.join(re.sub(r'[\u3400-\u9fff，。？！、：；]',' ',value).split())


def semantic_intent(question):
    if re.search(r'证明.*合规|适用|适合|可否|能否|是否.*合规|applicab|compliance',question,re.I):
        return 'applicability'
    if re.search(r'泄压|排气|气体|vent|gas release',question,re.I):
        return 'venting'
    if re.search(r'封装|包装|架构|布局|packaging|architecture',question,re.I):
        return 'packaging'
    if re.search(r'热|温度|thermal|temperature',question,re.I):
        return 'thermal'
    raise ValueError('Choose thermal risk, packaging, venting, or evidence applicability.')


def nifi_intent(question):
    if re.search(r'\b(start|stop|restart|delete|create|deploy|schedule|configure|change|yesterday|historical|last hour|last week)\b',question,re.I):
        raise ValueError('Only current read-only NiFi inspection is supported.')
    if re.search(r'昨天|历史|上周|上一小时|过去|重启|删除|创建|部署|修改|配置|调度|(?:^|请|帮我)(?:启动|停止)',question):
        raise ValueError('Only current read-only NiFi inspection is supported.')
    if re.search(r'公告|告警|警告|bulletin|warning',question,re.I):return 'bulletins'
    if re.search(r'拓扑|连接|关系图|topology|connection|graph',question,re.I):return 'topology'
    if re.search(r'无效|已停止|处理器|健康|invalid|stopped|processor|health',question,re.I):return 'health'
    if re.search(r'状态|概述|总结|运行|队列|排队|线程|流文件|status|summary|summarize|running|situation|queue|flowfile|thread',question,re.I):return 'status'
    raise ValueError('Choose current status, processor health, topology, or retained bulletins.')


if __name__ == '__main__':
    assert normalize_query('热隔离') == 'thermal containment'
    assert nifi_intent('哪些处理器无效或已停止？') == 'health'
    assert semantic_intent('热风险来自哪些证据？') == 'thermal'
    print('Bilingual query and display contracts OK')
