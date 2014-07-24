A simple minimal program to crawl a website to get (at least) 10 events, given a sample event page present on that website.

Do NOT use mindlessly: it's going to send dozens http requests at once.

I chose to write the downloading/crawling as asynchronous coroutines. This turned out not to be the best idea, since sending several http requests to the same server (for smaller/nimbler servers) will increase the amount of time needed to get the first complete response back apparently. Thus you won't see anything shown on the terminal for several seconds, don't worry and wait.


Installation
============

This requires Python > 3.4.0, to install simply run

`python3.4 setup.py install`

this might require root permissions, so to avoid it, create a virtualenv (if you haven't already)

Alternatively you can also install the dependencies (just `lxml` currently) with `pip install -r requirements.txt` and then proceed to import the modules/develop.

Once installed with setuptools, you should have the `eventcrawler` executable in your PATH

Just invoke it like `eventcrawler http://url.of.example.com/event/web/page`

This will output some logging information on the stderr, so to get only the 10 results you should expect you can also redirect just the stdout.

You can also access it directly from Python code with

```python
from eventcrawler import search_events
search_events('http://url.of.example.com/event/web/page')
```

This will return more than 10 results (since the downloads are started in parallel, I chose to process all of them, and then just filter the result)

