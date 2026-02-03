<!-- Source: https://www.python-httpx.org/ -->

# HTTPX

---

*A next-generation HTTP client for Python.*

HTTPX is a fully featured HTTP client for Python 3, which provides sync and async APIs, and support for both HTTP/1.1 and HTTP/2.

---

Install HTTPX using pip:

```
$ pip install httpx
```

Now, let's get started:

```
>>> import httpx
>>> r = httpx.get('https://www.example.org/')
>>> r
<Response [200 OK]>
>>> r.status_code
200
>>> r.headers['content-type']
'text/html; charset=UTF-8'
>>> r.text
'<!doctype html>\n<html>\n<head>\n<title>Example Domain</title>...'
```

Or, using the command-line client.

```
# The command line client is an optional dependency.
$ pip install 'httpx[cli]'
```

Which now allows us to use HTTPX directly from the command-line...

Sending a request...

## Features

HTTPX builds on the well-established usability of `requests`, and gives you:

* A broadly [requests-compatible API](compatibility/).
* Standard synchronous interface, but with [async support if you need it](async/).
* HTTP/1.1 [and HTTP/2 support](http2/).
* Ability to make requests directly to [WSGI applications](advanced/transports/#wsgi-transport) or [ASGI applications](advanced/transports/#asgi-transport).
* Strict timeouts everywhere.
* Fully type annotated.
* 100% test coverage.

Plus all the standard features of `requests`...

* International Domains and URLs
* Keep-Alive & Connection Pooling
* Sessions with Cookie Persistence
* Browser-style SSL Verification
* Basic/Digest Authentication
* Elegant Key/Value Cookies
* Automatic Decompression
* Automatic Content Decoding
* Unicode Response Bodies
* Multipart File Uploads
* HTTP(S) Proxy Support
* Connection Timeouts
* Streaming Downloads
* .netrc Support
* Chunked Requests

## Documentation

For a run-through of all the basics, head over to the [QuickStart](quickstart/).

For more advanced topics, see the **Advanced** section,
the [async support](async/) section, or the [HTTP/2](http2/) section.

The [Developer Interface](api/) provides a comprehensive API reference.

To find out about tools that integrate with HTTPX, see [Third Party Packages](third_party_packages/).

## Dependencies

The HTTPX project relies on these excellent libraries:

* `httpcore` - The underlying transport implementation for `httpx`.
* `h11` - HTTP/1.1 support.
* `certifi` - SSL certificates.
* `idna` - Internationalized domain name support.
* `sniffio` - Async library autodetection.

As well as these optional installs:

* `h2` - HTTP/2 support. *(Optional, with `httpx[http2]`)*
* `socksio` - SOCKS proxy support. *(Optional, with `httpx[socks]`)*
* `rich` - Rich terminal support. *(Optional, with `httpx[cli]`)*
* `click` - Command line client support. *(Optional, with `httpx[cli]`)*
* `brotli` or `brotlicffi` - Decoding for "brotli" compressed responses. *(Optional, with `httpx[brotli]`)*
* `zstandard` - Decoding for "zstd" compressed responses. *(Optional, with `httpx[zstd]`)*

A huge amount of credit is due to `requests` for the API layout that
much of this work follows, as well as to `urllib3` for plenty of design
inspiration around the lower-level networking details.

## Installation

Install with pip:

```
$ pip install httpx
```

Or, to include the optional HTTP/2 support, use:

```
$ pip install httpx[http2]
```

To include the optional brotli and zstandard decoders support, use:

```
$ pip install httpx[brotli,zstd]
```

HTTPX requires Python 3.9+