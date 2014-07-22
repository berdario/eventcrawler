from collections import deque

from pyquery import PyQuery as pq

base_targets = ['when', 'where', 'phone', 'price']

def find_nodes(targets, body):
    queue = deque([body])
    candidates = []
    while queue:
        node = queue.pop()
        if len(node):
            queue.extend(node)
        text = (node.text or '').lower()
        if text and any(t in text for t in targets):
            candidates.append(node)
    return candidates

def dates(body):
    pass

def main():
    s1 = 'http://events.stanford.edu/events/353/35309/'
    body = pq(s1)('body')[0]

    targets += dates(body)
    print(find_nodes(targets, body))
