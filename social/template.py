
import json

from mako.template      import Template
from mako.lookup        import TemplateLookup
from twisted.internet   import threads, defer
from twisted.python     import log


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

    if request.args.has_key("_ns"):
        request.addCookie("_ns", "1")

    if args.has_key("script") and args["script"]:
        args["noscriptUrl"] = request.path + "?_ns=1" \
                              if request.path == request.uri \
                              else request.uri + "&_ns=1"

    try:
        template = yield threads.deferToThread(_getTemplate, path)
        text = template.render(**args)
        request.write(text)
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


@defer.inlineCallbacks
def renderScriptBlock(request, path, dfn, tags=False, parent=None,
                      method=None, last=False, css=None, scripts=None,
                      handlers=None, **kw):
    try:
        template = yield threads.deferToThread(_getTemplate, path, dfn)
        text = template.render(**kw)
    except Exception, err:
        request.processingFailed(err)

    map = {"content": text, "node": parent, "method": method, "last": last,
           "css": [], "js": [], "resources": {}, "handlers": handlers}

    if css:
        for id, url in css:
            map["css"].append(id)
            map["resources"]["id"] = url

    if scripts:
        for id, url in scripts:
            map["js"].append(id)
            map["resources"]["id"] = url

    fmt = "<script>loader.load(%s);</script>\n" if tags else "loader.load(%s)\n"
    text = fmt % json.dumps(map)
    request.write(text)
