
from zope.interface   import Interface, Attribute

class IItemType(Interface):
    itemType = Attribute("Type of item")
    position = Attribute("Position in share tabbar")
    hasIndex = Attribute("Indicates if there are indexes on this type")

    def renderShareBlock(request, isAjax):
        """
        """

    def rootHTML(convId, args):
        """
        """

    def fetchData(args, convId=None):
        """
        """

    def create(request, myId, myOrgId):
        """
        """

    def getResource(isAjax):
        """
        """


class IAuthInfo(Interface):
    username = Attribute("User key")
    organization = Attribute("Key of the user's organization")
    isAdmin = Attribute("Flag to indicate if the user is an administrator")
    token = Attribute("Authenticity token used for CSRF busting")
