import os
import gobject
import gtk
import cairo
import rsvg
import wnck

import tempfile
import time

import cream
import cream.gui

FONT = ('Droid Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
FONT_SIZE = 14
COLOR = (.1, .1, .1, 1)
PADDING = 10
FADE_DURATION = 500

class Applet(gobject.GObject):

    __gtype_name__ = 'Applet'
    __gsignals__ = {
        'render-request': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_PYOBJECT, ()),
        'allocation-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        }

    def __init__(self):
        gobject.GObject.__init__(self)
        self.allocation = None
        self.position = None


    def draw(self):

        self.emit('render-request')


    def render(self, ctx):
        pass


    def set_position(self, x, y):
        self.position = (x, y)


    def get_position(self):
        return self.position


    def set_allocation(self, width, height):

        self.allocation = (width, height)
        self.emit('allocation-changed', self.get_allocation())


    def get_allocation(self):
        return self.allocation


    def allocate(self, height):
        width = 30
        self.set_allocation(width, height)
        return self.get_allocation()


class ClockApplet(Applet):

    def __init__(self):
        Applet.__init__(self)

        self.draw()

        gobject.timeout_add(1000, self.draw)


    def render(self, ctx):

        s = time.strftime('%H:%M')

        ctx.set_operator(cairo.OPERATOR_OVER)
        ctx.set_source_rgba(*COLOR)
        ctx.select_font_face(*FONT)
        ctx.set_font_size(FONT_SIZE)

        x_bearing, y_bearing, width, height = ctx.text_extents(s)[:4]
        ctx.move_to(PADDING, 24 - (24 - height) / 2)

        ctx.show_text(s)
        ctx.stroke()


    def allocate(self, height):

        s = time.strftime('%H:%M')

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, height)
        ctx = cairo.Context(surface)
        ctx.select_font_face(*FONT)

        ctx.set_font_size(FONT_SIZE)

        text_x_bearing, text_y_bearing, text_width, text_height = ctx.text_extents(s)[:4]

        self.set_allocation(text_width + text_x_bearing + 2*PADDING, height)
        return self.get_allocation()


class PanelWindow(gtk.Window):

    def __init__(self):

        gtk.Window.__init__(self)

        self._alpha = (.5, 1)

        # Setting up the Widget's window...
        self.stick()
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DOCK)
        self.set_keep_above(True)
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_resizable(False)
        self.set_colormap(self.get_screen().get_rgba_colormap())

        self.display = self.get_display()
        self.screen = self.display.get_default_screen()
        width, height = self.screen.get_width(), self.screen.get_height()

        self.set_size_request(width, 40)

        self.connect('expose-event', self.expose_cb)
        self.connect('realize', self.realize_cb)


    def set_alpha(self, bg, sdw):
        self._alpha = (bg, sdw)


    def get_alpha(self):
        return self._alpha


    def realize_cb(self, window):
        self.window.property_change("_NET_WM_STRUT", "CARDINAL", 32, gtk.gdk.PROP_MODE_REPLACE, [0, 0, 24, 0])
        self.window.input_shape_combine_region(gtk.gdk.region_rectangle((0, 0, self.get_size()[0], 24)), 0, 0)


    def expose_cb(self, source, event):
        """ Clear the widgets background. """

        ctx = source.window.cairo_create()

        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()

        ctx.scale(1440 / 10, 1)

        shadow_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.get_size()[0], self.get_size()[1])
        shadow_ctx = cairo.Context(shadow_surface)

        shadow = rsvg.Handle('shadow.svg')
        shadow.render_cairo(shadow_ctx)

        background_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.get_size()[0], self.get_size()[1])
        background_ctx = cairo.Context(background_surface)

        background = rsvg.Handle('background.svg')
        background.render_cairo(background_ctx)

        ctx.set_source_surface(shadow_surface)
        ctx.paint_with_alpha(self.get_alpha()[1])

        ctx.set_source_surface(background_surface)
        ctx.paint_with_alpha(self.get_alpha()[0])


class Panel():

    def __init__(self):

        self.applets = []

        self.screen = wnck.screen_get_default()
        self.screen.connect('viewports-changed', self.viewports_changed_cb)

        self.window = PanelWindow()
        self.window.show_all()

        self.window.connect('expose-event', self.expose_cb)

        gobject.timeout_add(200, self.handle_fullscreen_windows)

        self.add_applet(ClockApplet())


    def handle_fullscreen_windows(self):

        windows = self.screen.get_windows()
        workspace = self.screen.get_active_workspace()
        for w in windows:
            if w.is_maximized() and w.is_in_viewport(workspace):
                if self.window.get_alpha()[0] == .5:
    
                    def update(t, state):
                        self.window.set_alpha(.5 + state * .5, 1 - state)
                        self.window.window.invalidate_rect(gtk.gdk.Rectangle(0, 0, self.window.get_size()[0],self.window.get_size()[1]), True)
    
                    t = cream.gui.Timeline(FADE_DURATION, cream.gui.CURVE_SINE)
                    t.connect('update', update)
                    t.run()
                break
        else:
            if self.window.get_alpha()[0] == 1:

                def update(t, state):
                    self.window.set_alpha(1 - state * .5, state)
                    self.window.window.invalidate_rect(gtk.gdk.Rectangle(0, 0, self.window.get_size()[0],self.window.get_size()[1]), True)
    
                t = cream.gui.Timeline(FADE_DURATION, cream.gui.CURVE_SINE)
                t.connect('update', update)
                t.run()

        return True


    def add_applet(self, applet):

        applet.connect('render-request', self.render_request_cb)
        applet.connect('allocation-changed', self.allocation_changed_cb)

        self.applets.append(applet)
        applet.set_position(1000, 0)
        applet.allocate(24)
        applet.draw()


    def viewports_changed_cb(self, screen):
        self.handle_fullscreen_windows()


    def expose_cb(self, *args):

        ctx = self.window.window.cairo_create()

        for applet in self.applets:
            x, y = applet.get_position()
            width, height = applet.get_allocation()
            ctx.translate(x, y)
            ctx.rectangle(0, 0, width, height)
            ctx.clip()

            applet.render(ctx)


    def render_request_cb(self, applet):

        x, y = applet.get_position()
        width, height = applet.get_allocation()

        self.window.window.invalidate_rect(gtk.gdk.Rectangle(int(x), int(y), int(width), int(height)), True)

        ctx = self.window.window.cairo_create()

        ctx.translate(x, y)
        ctx.rectangle(0, 0, width, height)
        ctx.clip()
        applet.render(ctx)


    def allocation_changed_cb(self, applet, allocation):
        applet.set_position(1440 - allocation[0], 0)


if __name__ == '__main__':
    panel = Panel()
    gtk.main()
