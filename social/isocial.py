from zope.interface   import Interface, Attribute

class IItem(Interface):
    itemType = Attribute("Type of item")

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
