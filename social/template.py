
import json
import traceback

from mako.template      import Template
from mako.lookup        import TemplateLookup
from twisted.internet   import threads, defer
from twisted.python     import log


_collection = TemplateLookup(directories=['templates'],
                             module_directory='/tmp/social_templates',
                             output_encoding='utf-8',
                             default_filters=['decode.utf8'],
                             collection_size=100)


def _getTemplate(path, dfn=None):
    template = _collection.get_template(path)
    return template if not dfn else template.get_def(dfn)


@defer.inlineCallbacks
def render(request, path, *args, **data):
    kwargs = data

    if request.args.has_key("_ns"):
        request.addCookie("_ns", "1")

    if kwargs.has_key("script") and kwargs["script"]:
        kwargs["noscriptUrl"] = request.path + "?_ns=1" \
                              if request.path == request.uri \
                              else request.uri + "&_ns=1"

    try:
        template = yield threads.deferToThread(_getTemplate, path)
        text = template.render(*args, **kwargs)
        request.write(text)
    except Exception, err:
        log.msg(traceback.print_exc())
        request.processingFailed(err)


@defer.inlineCallbacks
def renderDef(request, path, dfn, *args, **data):
    try:
        template = yield threads.deferToThread(_getTemplate, path, dfn)
        text = template.render(*args, **data)
        request.write(text)
    except Exception, err:
        log.msg(traceback.print_exc())
        request.processingFailed(err)


@defer.inlineCallbacks
def renderScriptBlock(request, path, dfn, tags=False, parent=None,
                      method=None, last=False, css=None, scripts=None,
                      handlers=None, args=[], **data):
    try:
        template = yield threads.deferToThread(_getTemplate, path, dfn)
        text = template.render(*args, **data)
    except Exception, err:
        log.msg(traceback.print_exc())
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


def getBlock(path, dfn, args=[], **data):
    try:
        template = _getTemplate(path, dfn)
        text =  template.render(*args, **data)
        return text
    except Exception, err:
        log.msg(traceback.print_exc())
        raise Exception(err)
