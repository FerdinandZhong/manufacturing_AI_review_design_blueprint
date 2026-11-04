"""Explicit single-image paid build command. Ordinary prepare never calls this."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from pathlib import Path
from knowledge.openai_ocr import extract_image, OpenAIOCRUnavailable


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--allow-paid-openai-ocr', action='store_true',
                        help='Authorize at most one gpt-6-luna image request, with no retries')
    args = parser.parse_args(argv)
    try:
        blob = args.image.read_bytes()
    except OSError:
        parser.error('Cannot read the source image. Check the image path and file permissions.')
    try:
        result = extract_image(blob, allow_remote=args.allow_paid_openai_ocr)
    except (OpenAIOCRUnavailable, ValueError) as exc:
        parser.error(str(exc))
    print('Cached unverified OCR:', result['cache_key'])
    print('Run prepare.py to index this cache. OCR cannot establish engineering measurements or decisions.')


if __name__ == '__main__':
    assert callable(main)
    main()
