
from mako.template      import Template
from mako.lookup        import TemplateLookup
from twisted.internet   import threads, defer


_collection = TemplateLookup(directories=['templates'],
                             module_directory='/tmp/social_templates',
                             output_encoding='utf-8',
                             collection_size=100)


def _getTemplate(path, dfn=None):
    template = _collection.get_template(path)
    return template if not dfn else template.get_def(dfn)


@defer.inlineCallbacks
def render(request, path, **kw):
    args = kw
    args["noscript"] = False
    if request.args.has_key("noscript"):
        args["noscript"] = True
    else:
        args["noscriptUrl"] = request.path + "?noscript=1" \
                              if request.path == request.uri \
                              else request.uri + "&noscript=1"

    try:
        template = yield threads.deferToThread(_getTemplate, path)
        text = template.render(**args)

        request.setHeader('content-length', str(len(text)))
        request.write(text)
        request.finish()
    except Exception, err:
        request.processingFailed(err)


@defer.inlineCallbacks
def renderDef(request, path, dfn, **kw):
    try:
        template = yield threads.deferToThread(_getTemplate, path, dfn)
        text = template.render(**kw)
        request.write(text)
    except Exception, err:
        request.processingFailed(err)
