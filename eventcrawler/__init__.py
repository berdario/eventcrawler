import re
from collections import deque
from functools import partial
from urllib.parse import urlparse, urljoin
from urllib.request import urlopen
from urllib.error import HTTPError
from asyncio import async, coroutine, get_event_loop, as_completed

from lxml import html, etree

base_targets = ['when', 'where', 'phone', 'price', 'ticket']

date_targets = ['monday', 'tuesday', 'wednesday', 'thursday',
                'friday', 'saturday', 'sunday', 'january', 'february',
                'march', 'april', 'may', 'june', 'july', 'august',
                'september', 'october', 'november', 'december']

def _find_nodes(targets, targets_regexps, body):
    regexps = [re.compile(rtext, re.IGNORECASE) for rtext in targets_regexps]
    queue = deque([body])
    candidates = []
    minlen = len(min(targets, key=len))
    while queue:
        node = queue.pop()
        if len(node):
            queue.extend(node)
        text = (node.text or '').lower()
        if len(text) >= minlen and \
        (any(t in text for t in targets) or \
         any(r.match(text) for r in regexps)):
                candidates.append(node)
    return candidates

def filter_comments(nodes):
    return [node for node in nodes if not isinstance(node, etree.CommentBase)]

def get_hierarchy(node):
    def get_numbered_tag(node):
        if node.getparent() is not None:
            return node.tag + str(node.getparent().index(node))
        else:
            return node.tag
    parent = node.getparent()
    parents = [node]
    while parent is not None:
        parents.append(parent)
        parent = parent.getparent()
    return ">".join(get_numbered_tag(node) for node in reversed(parents))

@coroutine
def download(url):
    return html.parse(urlopen(url)).find('body')

@coroutine
def find_parent_page(urlstring):
    response = None
    url = urlparse(urlstring)
    base_url = url.scheme + '://' + url.netloc
    splitted_path = url.path.split('/')
    if not url.query:
        splitted_path = splitted_path[:-1]
    while not response:
        try:
            parent_page = urljoin(base_url, '/'.join(splitted_path))
            response = urlopen(parent_page)
        except HTTPError as e:
            if e.code == 404:
                pass
            else:
                raise
        splitted_path = splitted_path[:-1]
    return html.parse(response).find('body')

def find_links(body):
    url = urlparse(body.base_url)
    base_url = url.scheme + '://' + url.netloc
    return [n.attrib['href'] for n in body.xpath('.//a[@href]')
            if n.attrib['href'].startswith(base_url)]

regexps = ['20\d\d', r'\(?\d{3}\)?\-?\s?\d{3}-?\d{4}']
targets = base_targets + date_targets
find_nodes = partial(_find_nodes, targets, regexps)

def fingerprint_page(event_page):
    page_nodes = filter_comments(find_nodes(event_page))
    return {get_hierarchy(node) for node in page_nodes}

@coroutine
def crawl(links, visited, target_fingerprint):
    results = []
    while len(results) < 10 and len(links-visited) > 0:
        pages = as_completed([async(download(url)) for url in links - visited])
        visited.update(links)
        links = set()
        for future_page in pages:
            page = yield from future_page
            print('diff: ', target_fingerprint ^ fingerprint_page(page))
            if target_fingerprint == fingerprint_page(page):

                results.append(page.base_url)
            links.update(find_links(page))
    return results

@coroutine
def async_main():
    event_url = 'http://www.workshopsf.org/?page_id=140&id=1328'
    #'http://events.stanford.edu/events/353/35309/'
    future_event_page = async(download(event_url))
    future_event_parent = async(find_parent_page(event_url))
    event_page = yield from future_event_page
    event_parent = yield from future_event_parent
    fingerprint = fingerprint_page(event_page)
    links = set(find_links(event_parent))
    result = yield from crawl(links, {event_url}, fingerprint)
    return result

def main():
    hits = list(get_event_loop().run_until_complete(async_main()))
    print(*hits, sep='\n')
