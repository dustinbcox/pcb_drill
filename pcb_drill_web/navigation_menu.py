from flask import url_for
from werkzeug.routing import BuildError


class NavigationMenuItem(object):
    """ Menu item for the template """
    def __init__(self, title, name, **kwargs):
        """ Create new menu item
        Arguments:
            title - Text visable to menu
            name - name of the function and iternal reference
            **kwargs to pass in for url_for(name, **kwargs)"""
        self.title = title
        if name != "" or name is None:
            try:
                self.href = url_for(name, **kwargs)
            except BuildError:
                # This error was not obvious to me, so I made it obvious
                raise ValueError("Unable to locate URL for {0}.".format(name))
        else: # Empty name
            name = "#"
            self.href = "#"
        self.name = name
        self.active = False
        self.is_menu_item = True

 
class NavigationMenu(NavigationMenuItem):
    """ Contain the navigation menu for the website"""
    def __init__(self, title="", name="", **kwargs):
        self.menu = []
        NavigationMenuItem.__init__(self, title, name, **kwargs)
        self.is_menu_item = False
    def add(self, menu_item):
        self.menu.append(menu_item)
    def __iter__(self):
        return iter(self.menu)
    def set_active(self, title):
        """ Set a given title item as the active menu item"""
        if self.title == title:
            self.active = True
            return
        else:
            self.active = False
        for item in self.menu:
            if item.title == title:
                item.active = True
            else:
                item.active = False


