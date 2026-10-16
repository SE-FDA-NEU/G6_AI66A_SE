"""Private subprocess protocol: filesystem extraction only, never DB writes."""
import json
from pathlib import Path
import signal
import sys

from app.core.config import settings
from app.models import FileFormat
from app.services.reader_extraction import ReaderConversionError, prepare_reader


def main():
    work = Path(sys.argv[1])
    request = json.loads((work / 'request.json').read_text(encoding='utf-8'))
    settings.SOFFICE_BINARY = request['soffice_binary']
    settings.OFFICE_CONVERSION_TIMEOUT_SECONDS = request['conversion_timeout']
    # POSIX cancellation unwinds convert_office, which kills its own process
    # group. Windows cancellation kills the worker's entire tree with taskkill.
    def terminate(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    def report_pages(count):
        staged = work / 'page_count.tmp'
        staged.write_text(json.dumps({'page_count': count}), encoding='utf-8')
        staged.replace(work / 'page_count.json')
    try:
        result, rendered = prepare_reader(request['source'], FileFormat(request['format']), work,
                                          on_page_count=report_pages)
        rendered.rename(work / 'reader.pdf')
        response = {'result': result}
    except ReaderConversionError as error:
        response = {'error': {'code': error.code, 'message': str(error)}}
    except Exception:
        response = {'error': {'code': 'extraction_failed', 'message': 'Document extraction failed. Please retry.'}}
    (work / 'response.json').write_text(json.dumps(response, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
