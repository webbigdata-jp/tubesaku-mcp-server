"""Normalize published Markdown URLs without treating an origin as a path."""
import re
from urllib.parse import urlsplit
from services.agent_data import BASE_URL, RETIRED_MARKDOWN, TREND_FILES


def safe_md_path(path):
    path = path.strip()
    if path.startswith(BASE_URL + '/'):
        path = path[len(BASE_URL):]
    if path.lstrip('/') in TREND_FILES.values():
        path = '/llms/' + path.lstrip('/')
    if not path.startswith('/'):
        path = '/' + path
    if path.rsplit('/', 1)[-1] == RETIRED_MARKDOWN:
        raise ValueError('Live actuals dataset has been retired')
    if not path.endswith('.md'):
        raise ValueError('Only .md files are allowed')
    if path.startswith('//') or '..' in path or not re.fullmatch(r'/[a-zA-Z0-9_\-./]+\.md', path):
        raise ValueError('Invalid markdown path')
    return path


def listed_md_paths(text):
    paths = []
    for token in re.findall(r'https?://[^\s|)<>]+|(?<![\w/])/[a-zA-Z0-9_\-./]+\.md', text):
        if not token.endswith('.md'):
            continue
        parsed = urlsplit(token)
        if parsed.netloc and (parsed.scheme != 'https' or parsed.netloc != urlsplit(BASE_URL).netloc):
            continue
        if parsed.path.rsplit('/', 1)[-1] == RETIRED_MARKDOWN:
            continue
        paths.append(safe_md_path(parsed.path))
    return sorted(set(paths))
