import re
from collections import deque
from functools import partial
from urllib.parse import urlparse, urljoin
from urllib.request import urlopen
from urllib.error import HTTPError

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
        if node.getparent():
            return node.tag + str(node.getparent().index(node))
        else:
            return node.tag
    parent = node.getparent()
    parents = [node]
    while parent is not None:
        parents.append(parent)
        parent = parent.getparent()
    return ">".join(get_numbered_tag(node) for node in reversed(parents))

def download(url):
    return html.parse(urlopen(url)).find('body')

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
    return (parent_page, response)

def find_links(body):
    url = urlparse(body.base_url)
    base_url = url.scheme + '://' + url.netloc
    return [n.attrib['href'] for n in body.xpath('.//a[@href]')
            if n.attrib['href'].startswith(base_url)]


def main():
    s1 = 'http://events.stanford.edu/events/353/35309/'
    s2 = 'http://www.workshopsf.org/?page_id=140&id=1328'
    regexps = ['20\d\d', r'\(?\d{3}\)?\-?\s?\d{3}-?\d{4}']
    targets = base_targets + date_targets
    find_nodes = partial(_find_nodes, targets, regexps)
    body = pq(s2)('body')[0]


    n2 = filter_comments(find_nodes(body))
    s2check = pq('http://www.workshopsf.org/?cat=6')('body')[0]
    ncheck = filter_comments(find_nodes(s2check))
