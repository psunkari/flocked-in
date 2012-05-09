
import re
import json
import traceback
import tempfile
import os

from mako.template      import Template
from mako.lookup        import TemplateLookup

from social             import config


tmpDirName = 'social-' + str(os.geteuid())
tmpDirPath = os.path.join(tempfile.gettempdir(), tmpDirName)
filesystemChecks = False
try:
    checkForUpdates = config.get('Devel', 'CheckTemplateUpdates')
    if checkForUpdates and checkForUpdates.lower() == "true":
        filesystemChecks = True
except: pass

_collection = TemplateLookup(directories=['templates'],
                             module_directory=tmpDirPath,
                             output_encoding='utf-8',
                             input_encoding='utf-8',
                             filesystem_checks=filesystemChecks,
                             default_filters=['decode.utf8'],
                             collection_size=100)


_spaceRE = re.compile(r'(\n)\s+')


def warmupTemplateCache(templates):
    for path in templates:
        _collection.get_template(path)


def _getTemplate(path, dfn=None):
    template = _collection.get_template(path)
    return template if not dfn else template.get_def(dfn)


def render(request, path, *args, **data):
    kwargs = data

    if request.args.has_key("_ns"):
        request.addCookie("_ns", "1", path='/')

    if kwargs.has_key("script") and kwargs["script"]:
        kwargs["noscriptUrl"] = request.path + "?_ns=1" \
                              if request.path == request.uri \
                              else request.uri + "&_ns=1"

    template = _getTemplate(path)
    text = template.render(*args, **kwargs)
    request.write(_spaceRE.sub(r'\1', text))


def renderDef(request, path, dfn, *args, **data):
    template = _getTemplate(path, dfn)
    text = template.render(*args, **data)
    request.write(_spaceRE.sub(r'\1', text))


def renderScriptBlock(request, path, dfn, wrapInTags=False, parent=None,
                      method=None, last=False, css=None, scripts=None,
                      handlers=None, attrs={}, args=[], isIframe=False, **data):
    template = _getTemplate(path, dfn)
    text = template.render(*args, **data)
    text = _spaceRE.sub(r'\1', text)

    map = {"content": text, "node": parent, "method": method, "last": last,
           "css": [], "js": [], "resources": {}, "handlers": handlers}
    map.update(attrs)

    if css:
        for id, url in css:
            map["css"].append(id)
            map["resources"]["id"] = url

    if scripts:
        for id, url in scripts:
            map["js"].append(id)
            map["resources"]["id"] = url
    if isIframe:
        fmt = "<script>parent.$$.load(%s);</script>\n"
    elif wrapInTags:
        fmt = "<script>$$.load(%s);</script>\n"
    else:
        fmt = "$$.load(%s);\n"
    text = fmt % json.dumps(map)
    request.write(text)


def getBlock(path, dfn=None, args=[], **data):
    template = _getTemplate(path, dfn)
    text =  template.render(*args, **data)
    return _spaceRE.sub(r'\1', text)

