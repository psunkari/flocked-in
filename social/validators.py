import re
import formencode
from formencode         import validators,  ForEach, compound, api
from twisted.internet   import defer
from social             import utils, errors, _, db, constants, base, plugins
from social.isocial     import IAuthInfo
from social.relations   import Relation


class Invalid(api.Invalid):
    def  __init__(self, msg, value, state, error_list=None,
                  error_dict=None, data=None):
        self.data = data
        super(Invalid, self).__init__(msg, value, state,
                                      error_list, error_dict)


class Schema(formencode.Schema):
    """@to_python runs each validator in the schema and returns of the
    value/deferred or raises an Exception.

    The validator can either return a value or return a deferred.
    In case of deferred exceptions should be handled by Caller.
    If normal validation fails, exception object raised will also have
    deferred/successfully validated values, the deferred should again be
    checked for exceptions.
    """

    def _to_python(self, value_dict, state):
        """returns the values obtained from each validator.
        value can be a deferred depending on validator.
        Incase of errors, exception object will also have
        successfully validated arguments.
        Important: errors in deferred should be handled by caller.
        """
        if not value_dict:
            if self.if_empty is not api.NoDefault:
                return self.if_empty
            else:
                value_dict = {}

        for validator in self.pre_validators:
            value_dict = validator.to_python(value_dict, state)

        self.assert_dict(value_dict, state)

        new = {}
        errors = {}
        unused = self.fields.keys()
        if state is not None:
            previous_key = getattr(state, 'key', None)
            previous_full_dict = getattr(state, 'full_dict', None)
            state.full_dict = value_dict
        try:
            for name, value in value_dict.items():
                try:
                    unused.remove(name)
                except ValueError:
                    if not self.allow_extra_fields:
                        raise Invalid(
                           self.message('notExpected', state, name=repr(name)),
                           value_dict, state, data=new)
                    else:
                        if not self.filter_extra_fields:
                            new[name] = value
                        continue
                validator = self.fields[name]

                try:
                    new[name] = validator.to_python(value, state)
                except api.Invalid, e:
                    errors[name] = e

            for name in unused:
                validator = self.fields[name]
                try:
                    if_missing = validator.if_missing
                except AttributeError:
                    if_missing = api.NoDefault
                if if_missing is api.NoDefault:
                    if self.ignore_key_missing:
                        continue
                    if self.if_key_missing is api.NoDefault:
                        try:
                            message = validator.message('missing', state)
                        except KeyError:
                            message = name
                        errors[name] = MissingParam(str(message), None, state)
                    else:
                        try:
                            new[name] = validator.to_python(self.if_key_missing, state)
                        except api.Invalid, e:
                            errors[name] = e
                else:
                    new[name] = validator.if_missing

            for validator in self.chained_validators:
                if (not hasattr(validator, 'validate_partial')
                    or not getattr(validator, 'validate_partial_form', False)):
                    continue
                try:
                    validator.validate_partial(value_dict, state)
                except api.Invalid, e:
                    sub_errors = e.unpack_errors()
                    if not isinstance(sub_errors, dict):
                        # Can't do anything here
                        continue
                    formencode.schema.merge_dicts(errors, sub_errors)

            if errors:
                raise Invalid(
                    formencode.schema.format_compound_error(errors),
                    value_dict, state, error_dict=errors, data=new)

            for validator in self.chained_validators:
                new = validator.to_python(new, state)

            return new

        finally:
            if state is not None:
                state.key = previous_key
                state.full_dict = previous_full_dict


class ItemAccessDenied(api.Invalid):
    severity = 1

    def raiseError(self):
        raise errors.ItemAccessDenied(self.msg, self.value)


class EntityAccessDenied(api.Invalid):
    severity = 1

    def raiseError(self):
        raise errors.EntityAccessDenied(self.msg, self.value)


class InvalidRequest(api.Invalid):
    severity = 1

    def raiseError(self):
        raise errors.InvalidRequest(self.msg)


class InvalidItem(api.Invalid):
    severity = 2

    def raiseError(self):
        raise errors.InvalidItem(self.msg, self.value)


class InvalidItemType(api.Invalid):
    severity = 2

    def raiseError(self):
        raise errors.BaseError(self.msg, 400)


class InvalidEntity(api.Invalid):
    severity = 2

    def raiseError(self):
        raise errors.InvalidEntity(self.msg, self.value)


class InvalidTag(api.Invalid):
    severity = 2

    def raiseError(self):
        raise errors.InvalidTag(self.value)


class MissingParam(api.Invalid):
    severity = 3


class Item(validators.FancyValidator):
    columns = ['meta']
    itemType = None
    source = None
    arg = None
    checkAdmin = False

    @defer.inlineCallbacks
    def _to_python(self, itemId, state):
        itemType = self.itemType if self.itemType else 'item'
        if not itemId or not itemId[0]:
            raise MissingParam('%s-id' % (itemType), itemId, state)
        itemId = itemId[0]

        columns = set(['meta']).update(self.columns)
        item = yield db.get_slice(itemId, "items", columns)
        if not item:
            raise InvalidItem(itemType, itemId, state)

        item = utils.supercolumnsToDict(item)
        meta = item["meta"]

        if self.itemType and meta["type"] != self.itemType:
            raise InvalidItem(itemType, itemId, state)

        parentId = meta.get("parent", None)
        if parentId:
            parent = yield db.get_slice(parentId, "items", ["meta"])
            parent = utils.supercolumnsToDict(parent)
        else:
            parent = item
        acl = parent["meta"]["acl"]
        owner = parent["meta"]["owner"]
        #parent is deleted
        deleted = parent['meta'].get('state', None) == 'deleted'
        #item is deleted
        deleted = deleted or meta.get('state', None) == 'deleted'

        if deleted:
            raise InvalidItem(itemType, itemId, state)

        if self.source != 'api':
            request = state.request
            authInfo = request.getSession(IAuthInfo)
            myId = authInfo.username
            orgId = authInfo.organization
            isOrgAdmin = authInfo.isAdmin

        isOrgAdmin = self.checkAdmin and isOrgAdmin
        relation = Relation(myId, [])
        yield relation.initGroupsList()
        if not utils.checkAcl(myId, orgId, isOrgAdmin, relation, parent['meta']):
            raise ItemAccessDenied(itemType, itemId, state)
        defer.returnValue((itemId, item))


class Entity(validators.FancyValidator):
    entityType = ''
    columns = []
    source = ''

    @defer.inlineCallbacks
    def _to_python(self, entityId, state):
        if not entityId:
            raise MissingParam('%s-id' % (self.entityType), entityId, state)
        columns = ['basic']
        if self.columns:
            columns.extend(self.columns)
        entity = base.Entity(entityId)
        yield entity.fetchData(columns=columns)

        if not entity.basic or self.entityType != entity.basic['type']:
            raise InvalidEntity(self.entityType, entityId, state)

        if self.source != 'api':
            request = state.request
            orgId = request.getSession(IAuthInfo).organization
        org = entity.basic["org"] if entity.basic["type"] != "org" else entityId
        if orgId != org:
            raise EntityAccessDenied(entity.basic['type'], entityId, state)
        defer.returnValue(entity)


class TagString(validators.FancyValidator):
    _regex = '^[\w-]*$'

    def _to_python(self, tagName, state):
        if not tagName:
            raise MissingParam('Tag', tagName, state)

        decoded = tagName.decode('utf-8', 'replace')
        if len(decoded) > 50:
            raise InvalidRequest('Tag cannot be more than 50 characters long',
                                  tagName, state)
        if '_' in decoded or not re.match(self._regex, decoded):
            raise InvalidRequest('Tag can only include numerals, alphabet and hyphens (-)', tagName, state)
        return decoded


class Tag(validators.FancyValidator):
    source = None

    @defer.inlineCallbacks
    def _to_python(self, tagId, state):
        if not tagId:
            raise MissingParam('Tag-id', tagId, state)
        if self.source != 'api':
            request = state.request
            orgId = request.getSession(IAuthInfo).organization
        tag = yield db.get_slice(orgId, "orgTags", [tagId])
        if not tag:
            raise InvalidTag(tagId)

        tag = utils.supercolumnsToDict(tag)
        defer.returnValue((tagId, tag))


class TextWithSnippet(validators.FancyValidator):
    richText = False
    sanatize = True
    arg = 'comment'
    missingType = 'comment'
    snippet_length = constants.COMMENT_PREVIEW_LENGTH
    ignore_null = False

    def _to_python(self, value, state):
        request = state.request
        snippet, comment = utils.getTextWithSnippet(request, self.arg,
                                                    self.snippet_length,
                                                    richText=self.richText)
        if not comment and not self.ignore_null:
            raise MissingParam(self.missingType, value, state)
        return (comment, snippet)


class SocialString(validators.FancyValidator):
    multivalued = False
    sanitize = True

    def _to_python(self, value, state):
        return utils.getString(value, self.sanitize, self.multivalued)


class ValidConvType(validators.FancyValidator):
    def _to_python(self, value, state):
        if value not in plugins:
            #raise api.Invalid('Unsupported item type', value, state)
            raise InvalidItemType('Unsupported item type', value, state)
        return value


class URL(validators.FancyValidator):
    add_http = True
    not_empty = True
    messages = {'empty': _('url'),
                'missing': _('url')}

    def _to_python(self, value, state):
        if not value:
            raise MissingParam('url', value, state)
        try:
            return validators.URL(add_http=self.add_http).to_python(value)
        except api.Invalid:
            raise InvalidRequest('Invalid Url', value, state)

        raise InvalidRequest('Invalid Url', value, state)

class PollOptions(validators.FancyValidator):
    def _to_python(self, value, state):
        options = SocialString(multivalued=True).to_python(value)
        options = [x for x in options if x]
        options = utils.uniqify(options)
        if not options:
            raise MissingParam('options', value, state)
        if len(options) < 2:
            raise MissingParam('2nd option', value, state)
        return options


class SocialSchema(Schema):
    _pg = SocialString(if_missing='')
    _tk = SocialString(if_missing='')
    allow_extra_fields = True


class ValidateComment(SocialSchema):
    parent = Item(arg='parent')
    comment = TextWithSnippet()
    _review = compound.Pipe(SocialString(if_missing=0), validators.Int())
    fId = SocialString(if_missing=[], multivalued=True, sanitize=False)
    nc = validators.String()
    allow_extra_fields = True


class ValidateItem(SocialSchema):
    id = Item(arg='id')
    allow_extra_fields = True


class ValidateTag(SocialSchema):
    id = Item(arg='id', columns=['tags'])
    tag = compound.Pipe(SocialString(if_missing=''), TagString())


class ValidateTagId(SocialSchema):
    tag = compound.Pipe(SocialString(if_missing=None), Tag())
    id = Item(arg='id', columns=['tags'])


class NewItem(SocialSchema):
    type = compound.Pipe(SocialString(if_missing=None),
                         ValidConvType())


class ItemResponses(SocialSchema):
    id = Item(arg='id', columns=['tags'])
    start = SocialString(if_missing='')
    nc = compound.Pipe(SocialString(if_missing='0'),
                      validators.Int())


class State(object):
    pass


def raise_errors(errors_dict):
    items = sorted(errors_dict.items(), key=lambda x: getattr(x[1], 'severity', 3))

    highest_severity = getattr(items[0][1], 'severity', 3)
    errors_ = [items[0]]
    for name, error in items[1:]:
        if getattr(error, 'severity', 3) == highest_severity:
            errors_.append((name, error))
    missing_params = []
    for name, error in errors_:
        severity = getattr(error, 'severity', 3)
        if severity in (1, 2):
            error.raiseError()
        elif severity == 3:
            if isinstance(error, (MissingParam, api.Invalid)):
                missing_params.append(error.msg.encode('utf8', 'replace'))
    if missing_params:
        raise errors.MissingParams(missing_params)


class Validate(object):
    def __init__(self, schema):
        self._schema = schema

    def __call__(self, func):
        @defer.inlineCallbacks
        def wrapper(cls, request, *args, **kwargs):
            state = State()
            state.request = request
            deferreds = []
            data = {}
            error_dict = {}
            try:
                data = self._schema.to_python(request.args, state)
            except api.Invalid as e:
                error_dict.update(e.error_dict)
                data = e.data

            for key in data:
                if isinstance(data[key], defer.Deferred):
                    try:
                        data[key] = yield data[key]
                    except api.Invalid as e:
                        error_dict[key] = e
            if error_dict:
                raise_errors(error_dict)
            kwargs['data'] = data
            d = func(cls, request, *args, **kwargs)
            if isinstance(d, defer.Deferred):
                retval = yield d
                defer.returnValue(retval)
            else:
                defer.returnValue(d)
        return wrapper
