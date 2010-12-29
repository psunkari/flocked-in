
from mako.template      import Template
from mako.lookup        import TemplateLookup
from twisted.internet   import threads
from twisted.python     import log


_collection = TemplateLookup(directories=['templates'],
                             module_directory='/tmp/social_templates',
                             output_encoding='utf-8',
                             collection_size=100)


def _render(path, **kw):
    template = _collection.get_template(path)
    return template.render(**kw)


def render(request, path, **kw):
    d = threads.deferToThread(_render, path, **kw)

    def _callback(text):
        request.setHeader('content-length', str(len(text)))
        request.write(text)
        request.finish()
    def _errback(err):
        request.processingFailed(err)
    d.addCallbacks(_callback, _errback)
