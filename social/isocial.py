
from zope.interface   import Interface, Attribute


class IItemType(Interface):
    itemType = Attribute("Type of item")
    position = Attribute("Position in share tabbar")
    hasIndex = Attribute("Indicates if there are indexes on this type")
    indexFields = Attribute("Fields indexes for text search")
    monitoredFields = Attribute("Fields monitored for keywords")

    def renderShareBlock(request, isAjax):
        """Render that static block that is used to
        share an item of this type
        """

    def rootHTML(convId, args):
        """Render the contents of this item. All required data must
        already have been fetched through a call to fetchData.
        """

    def fetchData(args, convId=None):
        """Fetch all data that is required to render this item. This
        function must avoid fetching entities and must return a list
        of entities that are required for rendering this item
        """

    def create(request, myId, myOrgId):
        """Create a new item of this type.
        All necessary data is extracted from the request.
        """

    def getResource(isAjax):
        """A resource that would handle any requests that are specific
        to this item.  Eg: Poll will need a resource to handle votes and
        events will need to handle RSVP;
        """


class IFeedUpdateType(Interface):
    updateType = Attribute("Type of update")

    def parse(updates):
        """Parse the given list of updates and return a tuple containing
        list of items and entities that need to be fetched
        """

    def reason(updates, data):
        """Build a reason string and list of userIds from the given
        list of reasons and the data that is passed.
        """


class IAuthInfo(Interface):
    username = Attribute("User key")
    organization = Attribute("Key of the user's organization")
    isAdmin = Attribute("Flag to indicate if the user is an administrator")
    token = Attribute("Authenticity token used for CSRF busting")
