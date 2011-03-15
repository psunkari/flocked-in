
from zope.interface   import Interface, Attribute

class IItemType(Interface):
    itemType = Attribute("Type of item")
    position = Attribute("Position in share tabbar")
    hasIndex = Attribute("Indicates if there are indexes on this type")

    def shareBlockProvider():
        """
        """

    def rootHTML(convId, args):
        """
        """

    def fetchData(args, convId=None):
        """
        """

    def renderRoot(request, convId, args):
        """
        """

    def create(request):
        """
        """

    def post(request):
        """
        """


class IAuthInfo(Interface):
    username = Attribute("User key")
    organization = Attribute("Key of the user's organization")
    isAdmin = Attribute("Flag to indicate if the user is an administrator")
