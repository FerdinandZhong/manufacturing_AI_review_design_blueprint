"""Bounded cited-claim grammar for semantic narration.

This is a deliberately small claim language, not a general entailment model.
Unknown prose falls back. Review summaries use complete authoritative statements.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re


def validate_narration(generated, authoritative):
    """Accept complete approved review statements, with flexible whitespace."""
    if not isinstance(generated, str) or not generated.strip() or len(generated)>20000:
        raise ValueError('Empty or oversized narration')
    normalize = lambda value: re.sub(r'\s+', ' ', value).strip()
    # A model may select and reorder complete approved bullets/sentences.
    approved = {normalize(line) for line in re.split(r'\n|(?<=\.)\s+', authoritative) if line.strip()}
    lines = [normalize(line) for line in re.split(r'\n|(?<=\.)\s+', generated) if line.strip()]
    if not lines or any(line not in approved for line in lines):
        raise ValueError('Narration contains statements outside the authoritative claim set')
    return generated


def validate_answer(generated, packet):
    """Accept only cited factual clauses from explicit subject/predicate schemas."""
    if not isinstance(generated,str) or not generated.strip() or len(generated)>5000:
        raise ValueError('Empty or oversized narration')
    facts = {fact['id']:fact for fact in packet['facts']}
    assets = {asset['id']:asset for asset in packet['records']['evidence']}
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n', generated) if s.strip()]
    for sentence in sentences:
        match = re.fullmatch(r'(.+?)\s*\[([A-Za-z0-9_-]+)\][.!]?',sentence)
        if not match:
            raise ValueError('Each claim requires exactly one bound citation')
        text, citation = match.groups()
        if citation in facts:
            value = re.escape(facts[citation]['value'])
            # Each grammar binds subject, property, value, polarity, and unit together.
            patterns = {
                'F-TEST': rf'(?:Atlas|The Atlas program) (?:has|shows|records) (?:a |an )?{value} thermal (?:bench )?(?:result|test result)',
                'F-RISK': rf'(?:Atlas|The Atlas program) (?:has|shows|records) (?:a |an )?{value} (?:thermal )?(?:design-risk|risk) (?:band|rating)',
                'F-REQ': rf'(?:Atlas|The Atlas program) (?:has|specifies|requires) (?:a |an )?thermal (?:target|requirement) (?:of |at )?{value}',
                'F-REF': rf'(?:The external study|The published study) (?:contains|reports|provides) {value} (?:published )?experiments',
            }
            pattern = patterns.get(citation)
            if not pattern or not re.fullmatch(pattern,text,flags=re.I):
                raise ValueError('Claim is outside the supported fact grammar')
        elif citation in assets:
            asset = assets[citation]
            caption = asset.get('caption',asset.get('caption_text','')).strip().rstrip('.!')
            # Generic source labels carry no image-derived measurements or findings.
            if text.lower() not in {'image reference','source image reference','external reference image','source reference'} and text != caption:
                raise ValueError('Source claim is not an approved description')
        else:
            raise ValueError('Unknown citation')
    return generated


if __name__ == '__main__':
    packet={'facts':[{'id':'F-TEST','value':'MARGINAL'}], 'records':{'evidence':[]}}
    assert validate_answer('Atlas shows a MARGINAL thermal result [F-TEST].',packet)
    try:
        validate_answer('Atlas shows a PASS thermal result [F-TEST].',packet)
        assert False
    except ValueError:
        pass
