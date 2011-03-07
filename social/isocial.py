from zope.interface   import Interface, Attribute

class IItem(Interface):
    itemType = Attribute("Type of item")
    position = Attribute("position in shared-block")
    hasIndex = Attribute("")

    def getRoot(myKey, convId):
        """
        """
    def renderRoot(request, convId, args):
        """
        """
    def action(myKey):
        """
        """
    def create(request):
        """
        """
    def post(request):
        """
        """
