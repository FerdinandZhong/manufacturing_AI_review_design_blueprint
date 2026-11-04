# Published battery evidence

Source: Golubkov et al. (2018), *Thermal runaway of large automotive Li-ion batteries*, RSC Advances, DOI [10.1039/C8RA06458J](https://doi.org/10.1039/C8RA06458J).

License: [Creative Commons Attribution 3.0](https://creativecommons.org/licenses/by/3.0/), recorded in the source XML permissions. Full author attribution appears in `manifest.json` and the displayed source excerpt.

- `source.xml`: Europe PMC source XML, retained unchanged.
- `cell-before-after.jpg`: original Figure 2 bytes. The caption provides no numbered experiment identity.
- `experiment-7.jpg`: original Figure 13 bytes. The caption explicitly identifies experiment 7.
- `experiments.csv`: selected values from Table 2. Chemistry comes from Table 1. This is a table extraction, not simulated data.
- `source-excerpt.txt`: selected table definitions, rows, and figure captions extracted as plain text.
- `manifest.json`: source URLs, author attribution, license, checksums, extraction details, and source-located asset links.

The figures were retrieved through Europe PMC's article asset endpoint. Their bytes match the image MD5 metadata in the source XML.
Figures remain unmodified. The text and CSV are explicitly identified extractions.

Rebuild the derived package offline:

```bash
python 02_backend/scripts/build_research_reference.py
python 02_backend/knowledge/kb.py
```

The experiment measurements concern external LMO cells. They do not measure Atlas components or certify the synthetic NMC811 design.
Peak cell case temperature is an absolute measurement. It is not interchangeable with Atlas's synthetic thermal margin basis.
