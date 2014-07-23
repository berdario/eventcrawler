import re
from collections import deque

import lxml
from pyquery import PyQuery as pq

base_targets = ['when', 'where', 'phone', 'price']

date_targets = ['monday', 'tuesday', 'wednesday', 'thursday',
                'friday', 'saturday', 'sunday', 'january', 'february',
                'march', 'april', 'may', 'june', 'july', 'august',
                'september', 'october', 'november', 'december']

def find_nodes(targets, targets_regexps, body):
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
    return [node for node in nodes if not isinstance(node, lxml.etree.CommentBase)]

def parents(node):
    parent = node.getparent()
    parents = []
    while parent:
        parents.append(parent)
        parent = parent.getparent()
    return list(reversed(parents))

def main():
    s1 = 'http://events.stanford.edu/events/353/35309/'
    s2 = 'http://www.workshopsf.org/?page_id=140&id=1328'
    body = pq(s2)('body')[0]

    targets = base_targets + date_targets
    print(find_nodes(targets, ['20\d\d'], body))
