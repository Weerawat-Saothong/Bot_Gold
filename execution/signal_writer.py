import os
import logging
from config import PATH_SIGNAL

logger = logging.getLogger(__name__)


def write_signal(signal, sl=None, tp=None, lot=None):

    path = PATH_SIGNAL

    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Prepare content
    if signal == "NONE":
        content = "NONE"
    else:
        if lot is not None:
            content = f"{signal},{sl},{tp},{lot}"
        else:
            content = f"{signal},{sl},{tp}"

    try:
        # Write using platform ANSI on Windows to match EA's FILE_ANSI expectation.
        # On Windows 'mbcs' maps to the ANSI code page; on other OSes fall back to utf-8.
        enc = 'mbcs' if os.name == 'nt' else 'utf-8'
        with open(path, "w", encoding=enc) as f:
            f.write(content)
        logger.info(f"Wrote signal to {path}: {content}")
    except Exception as e:
        logger.error(f"Failed to write signal to {path}: {e}")
