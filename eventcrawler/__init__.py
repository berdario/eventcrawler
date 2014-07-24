import re
from sys import argv, stderr
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

regexps = ['20\d\d', r'\(?\d{3}\)?\-?\s?\d{3}-?\d{4}']
targets = base_targets + date_targets


def _find_nodes(targets, targets_regexps, body):
    """Get all the interesting node in the page body
    Interesting nodes are those which contain the target words"""
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
           (any(t in text for t in targets) or
            any(r.match(text) for r in regexps)):
                candidates.append(node)
    return candidates

find_nodes = partial(_find_nodes, targets, regexps)


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


def blocking_download(url):
    try:
        return html.parse(urlopen(url)).find('body')
        # should add user agent
        # and also we should honor the robots.txt
        # and care about rate limiting
    except HTTPError as e:
        if e.code == 404:
            print(url, 'was a 404', file=stderr)
            return
        else:
            raise

download = coroutine(blocking_download)


@coroutine
def find_parent_page(urlstring):
    """Finds the first parent page that's not a 404
    used as a starting point for the crawler"""
    response = None
    url = urlparse(urlstring)
    base_url = url.scheme + '://' + url.netloc
    splitted_path = [s for s in url.path.split('/') if s]
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
    """Get all the links (absolute or relative) pointing internally towards the same site"""
    url = urlparse(body.base_url)
    domain = url.scheme + '://' + url.netloc

    def add_base_url(url):
        if '://' not in url:
            return urljoin(body.base_url, url)
        else:
            return url

    def select_url(url):
        return (url.startswith(domain) or '://' not in url) and \
            not url.startswith('javascript:') and not url.startswith('mailto:')

    links = [add_base_url(u.attrib['href']) for u in body.xpath('.//a[@href]')]
    return set(filter(select_url, links))


def fingerprint_page(event_page):
    """Returns the set of hierarchies for each interesting node"""
    page_nodes = filter_comments(find_nodes(event_page))
    return {get_hierarchy(node) for node in page_nodes}


def levenshtein(s1, s2):
    """Courtesy of wikibooks: http://en.wikibooks.org/wiki/Algorithm_Implementation/Strings/Levenshtein_distance#Python"""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    # len(s1) >= len(s2)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1 # j+1 instead of j since previous_row and current_row are one character longer
            deletions = current_row[j] + 1       # than s2
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def score_candidate(page, target_fingerprint):
    """The more the interesting nodes are in the same place/structure in the page,
    the more their hierarchy string representation should be similar.

    In some lucky cases the nodes might be in the exact same positions, so that the
    two sets/fingerprints will be the same, otherwise we'll try to check the distance for
    every product/combinations of the hierarchy-strings not present in the other
    fingerprint, but only if there're less than 37 such pairings"""
    fingerprint = fingerprint_page(page)
    # if any of the 2 symmetric differences are empty, use the shortest string
    # from the other set, this is to avoid penalizing too much pages that have
    # fewer interesting nodes than the target page (for example)
    d1 = target_fingerprint - fingerprint or {min(fingerprint, key=len)}
    d2 = fingerprint - target_fingerprint or {min(target_fingerprint, key=len)}
    distance = None
    if len(d1)*len(d2) < 37:
        distance = sum(min(levenshtein(x, y) for y in d2) for x in d1)
        if 'events' in urlparse(page.base_url).path:
            distance /= 2
    print('distance:', distance, 'url:', page.base_url, file=stderr)
    return distance


def sample_candidates(links, target_fingerprint):
    """Get the average score for the first 5 candidates, so as to pick a
    threshold for the crawling function"""
    samples = []
    while links:
        new_links = set()
        for url in links:
            page = blocking_download(url)
            new_links.update(find_links(page))
            sample = score_candidate(page, target_fingerprint)
            if sample is not None:
                samples.append(sample)
            if len(samples) == 5:
                # clip to 10, in case the first few samples are too
                # good compared to the following ones
                return max(sum(samples)/5, 10)
        else:
            links = new_links


@coroutine
def crawl(links, visited, target_fingerprint):
    results = []
    sample_average = sample_candidates(links, target_fingerprint)
    print('average score:', sample_average, file=stderr)
    # if we exhaust the links on the website, we will
    # exit from the loop even with < 10 results
    while len(results) < 10 and len(links - visited) > 0:
        pages = as_completed([download(url) for url in links - visited])
        visited.update(links)
        links = set()
        for future_page in pages:
            page = yield from future_page
            if page is None:
                continue
            score = score_candidate(page, target_fingerprint)
            if score is not None and score < sample_average:
                # a running average might be better, but this will do for now
                results.append((score, page.base_url))
            links.update(find_links(page))
    return [url for score, url in sorted(results)]


@coroutine
def async_main(event_url):
    future_event_page = async(download(event_url))
    future_event_parent = async(find_parent_page(event_url))
    event_page = yield from future_event_page
    event_parent = yield from future_event_parent
    fingerprint = fingerprint_page(event_page)
    links = find_links(event_parent)
    result = yield from crawl(links, {event_url}, fingerprint)
    return result


def search_events(page):
    return list(get_event_loop().run_until_complete(async_main(page)))


def main():
    hits = search_events(argv[1])
    print(*hits[:10], sep='\n')
