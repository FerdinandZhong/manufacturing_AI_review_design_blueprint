"""Build the pinned CC BY 3.0 study package offline from publisher XML and figures."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).parents[1] / 'knowledge/reference_data'
SOURCE_ID = 'RSC-C8RA06458J'
SOURCE_URL = 'https://pmc.ncbi.nlm.nih.gov/articles/PMC9091216/'
LICENSE = 'https://creativecommons.org/licenses/by/3.0/'
ATTRIBUTION = ('Andrey W. Golubkov, René Planteu, Philipp Krohn, Bernhard Rasch, '
               'Bernhard Brunnsteiner, Alexander Thaler and Viktor Hacker (2018). '
               'Thermal runaway of large automotive Li-ion batteries. RSC Advances. '
               'DOI: 10.1039/C8RA06458J. CC BY 3.0.')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(node):
    return ' '.join(''.join(node.itertext()).split())


def build():
    root = ET.parse(ROOT / 'source.xml').getroot()
    assert LICENSE in ET.tostring(root.find('.//permissions'), encoding='unicode')
    table = root.find('.//table-wrap[@id="tab2"]')
    source_rows = [[text(c) for c in row.findall('td')] for row in table.findall('.//tbody/tr')]
    assert len(source_rows) == 11 and all(len(row) == 17 for row in source_rows)
    fields = ['source_id','experiment_id','method','chemistry','peak_cell_temperature_c',
              'total_gas_mol','initial_voltage_v','locator','review_status']
    with (ROOT / 'experiments.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in source_rows:
            writer.writerow(dict(zip(fields,[SOURCE_ID,row[0],row[1],'LMO',row[8],row[12],row[2],
                                             'Table 2, experiment '+row[0], 'Verified against source XML table cells'])))
    assert source_rows[6][8] == '500' and source_rows[10][12] == '5.9'
    excerpts = [ATTRIBUTION, 'Source: '+SOURCE_URL, 'License: '+LICENSE,
                'Extraction: selected source table and captions; figure files remain unmodified.',
                'Table 1 — Cell specification', text(root.find('.//table-wrap[@id="tab1"]')),
                'Table 2 — Definitions', text(table.find('caption')),
                'Table 2 — Rows (original column order)',
                ' | '.join(text(c) for c in table.findall('.//thead/tr/th'))]
    excerpts.extend(' | '.join(row) for row in source_rows)
    for fig in ['fig2','fig13']:
        excerpts.append(text(root.find(f'.//fig[@id="{fig}"]/caption')))
    (ROOT / 'source-excerpt.txt').write_text('\n\n'.join(excerpts)+'\n')
    assets = []
    specs = [
        ('RES-cell-before-after','cell-before-after.jpg','Cell before and after thermal runaway','image','image/jpeg','Fig. 2',[],
         'Published before/after cell photograph. The source does not assign this image to a numbered experiment.', ['thermal_response','venting']),
        ('RES-experiment-7','experiment-7.jpg','Experiment 7 — temperature, pressure, and gas release','image','image/jpeg','Fig. 13',['7'],
         'Published curves for experiment 7, one-sided heating. Join to Table 2 row 7 by source ID and experiment number.', ['thermal_response','venting']),
        ('RES-study-excerpt','source-excerpt.txt','Study definitions, experiment table, and figure captions','text','text/plain','Tables 1–2; Figs. 2 and 13',[str(i) for i in range(1,12)],
         'Source excerpts define the measured quantities and document all eleven experiments. Numeric data are external LMO-cell measurements.', ['thermal_response','venting','transferability'])]
    for aid,file,title,modality,mime,locator,ids,caption,concepts in specs:
        assets.append(dict(id=aid,file=file,title=title,modality=modality,mime_type=mime,locator=locator,
                           experiment_ids=ids,caption=caption,concepts=concepts,source_id=SOURCE_ID,
                           source_url=SOURCE_URL+('#'+('fig13' if aid=='RES-experiment-7' else 'fig2' if modality=='image' else 'tab2')),
                           sha256=digest(ROOT/file),author='Golubkov et al.',license='CC BY 3.0',license_url=LICENSE,
                           applicability='External LMO cell study; not Atlas NMC811 validation or a pack acceptance threshold.',
                           review_status='Source-locator and table-cell verification',unit='See Table 2 definitions'))
    # EuropePMC image-md5 metadata verifies the exact retrieved original figure bytes.
    expected = {'cell-before-after.jpg':'8c53d3b5f9156c441a600a604ec20daa','experiment-7.jpg':'8d3046ece816d7592aa6b97c8604ef44'}
    for file,md5 in expected.items():
        assert hashlib.md5((ROOT/file).read_bytes()).hexdigest() == md5
    manifest = dict(source_id=SOURCE_ID,title='Thermal runaway of large automotive Li-ion batteries',
                    doi='10.1039/C8RA06458J',source_url=SOURCE_URL,license_url=LICENSE,attribution=ATTRIBUTION,
                    chemistry='LMO',assets=assets,measurements_sha256=digest(ROOT/'experiments.csv'),
                    source_xml_sha256=digest(ROOT/'source.xml'),
                    retrieval_url='https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9091216/fullTextXML',
                    figure_retrieval_url='https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9091216/supplementaryFiles',
                    extraction='Table 2 columns No, Type, Vbefore_cell, Tmax_cell and nV; chemistry from Table 1. Source values retained; no interpolation.',
                    expected_row_count=11,measurements_file='experiments.csv',
                    units={'peak_cell_temperature_c':'degC (maximum cell case temperature)', 'total_gas_mol':'mol (overall released gas)', 'initial_voltage_v':'V'},
                    boundary='External cell measurements are not equivalent to the synthetic Atlas thermal margin basis. Figure 2 has no numbered experiment identity.')
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    first = build()
    assert first == build(), 'Reference rebuild must be deterministic'
    assert len(first['assets']) == 3
    print('Research reference OK: 11 published experiment rows, 2 original figures, 1 source excerpt')
