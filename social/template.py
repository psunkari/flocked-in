
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
    args = kw
    args["noscript"] = False
    if request.args.has_key("noscript"):
        args["noscript"] = True
    else:
        args["noscriptUrl"] = request.path + "?noscript=1" \
                              if request.path == request.uri \
                              else request.uri + "&noscript=1"
    d = threads.deferToThread(_render, path, **args)

    def _callback(text):
        request.setHeader('content-length', str(len(text)))
        request.write(text)
        request.finish()
    def _errback(err):
        request.processingFailed(err)
    d.addCallbacks(_callback, _errback)
    return d


def _renderDef(path, dfn, **kw):
    template = _collection.get_template(path)
    definition = template.get_def(dfn)
    return definition.render(**kw)


def renderDef(request, path, dfn, **kw):
    d = threads.deferToThread(_renderDef, path, dfn, **kw)

    def _callback(text):
        request.write(text)
    def _errback(err):
        request.processingFailed(err)
    d.addCallbacks(_callback, _errback)
    return d
