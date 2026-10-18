"""Run blocking conversion/extraction with cancellation and no child DB access."""
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from app.services.reader_extraction import ReaderConversionError, reader_representation, sha256


@dataclass
class PreparedExtraction:
    data: dict
    rendered: Path
    work: object = None

    def close(self):
        if self.work is not None:
            self.work.cleanup()


async def stop_worker(process):
    if process.returncode is not None:
        return
    if os.name == 'nt':
        killer = await asyncio.create_subprocess_exec(
            'taskkill', '/PID', str(process.pid), '/T', '/F',
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        await killer.wait()
    else:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
    await process.wait()


async def prepare_document(document, on_page_count=None):
    """Prepare metadata privately; the parent publishes it only on success."""
    source = Path(document.storage_path)
    if not source.is_file():
        raise ReaderConversionError('source_missing', 'The original file is missing.')
    try:
        path, reference = reader_representation(document)
        if reference['source_sha256'] == sha256(source):
            if on_page_count:
                on_page_count(document.page_count)
            return PreparedExtraction({'page_count': document.page_count,
                                       'extracted_text': document.extracted_text}, path)
    except ReaderConversionError:
        pass
    # Keep the cancellable Python extraction worker in an isolated workspace.
    work = tempfile.TemporaryDirectory(prefix='documind-job-')
    work_path = Path(work.name)
    request = {'source': str(source.resolve()), 'format': document.file_format.value}
    process = None
    try:
        started = asyncio.get_running_loop().time()
        (work_path / 'request.json').write_text(json.dumps(request), encoding='utf-8')
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'app.services.extraction_worker', str(work_path.resolve()),
            cwd=str(Path(__file__).resolve().parents[2]), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, **options)
        # The child reports physical page count before extracting page text.
        # Tighten the deadline immediately, counting conversion/startup time.
        # The parent is the only process allowed to update JobFile/Document.
        async with asyncio.timeout(300) as deadline:
            reported = False
            while process.returncode is None:
                progress = work_path / 'page_count.json'
                if not reported and on_page_count and progress.is_file():
                    count = json.loads(progress.read_text(encoding='utf-8'))['page_count']
                    budget = on_page_count(count)
                    deadline.reschedule(started + budget)
                    reported = True
                await asyncio.sleep(.02)
            await process.wait()
        response_path = work_path / 'response.json'
        if process.returncode or not response_path.is_file():
            raise ReaderConversionError('extraction_failed', 'Document extraction failed. Please retry.')
        response = json.loads(response_path.read_text(encoding='utf-8'))
        if 'error' in response:
            error = response['error']
            if error['code'] == 'conversion_timed_out':
                raise TimeoutError('Office conversion timed out.')
            raise ReaderConversionError(error['code'], error['message'])
        return PreparedExtraction(response['result'], work_path / 'reader.pdf', work)
    except BaseException:
        if process is not None:
            await stop_worker(process)
        work.cleanup()
        raise
