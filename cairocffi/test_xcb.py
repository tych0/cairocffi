# coding: utf8
"""

    cairocffi.test_xcb
    ~~~~~~~~~~~~~~~~~~

    Test suite for cairocffi.xcb.

    :copyright: Copyright 2013 by Simon Sapin
    :license: BSD, see LICENSE for details.

"""
import time
import xcffib
import xcffib.xproto
from xcffib.testing import XvfbTest
from xcffib.xproto import ConfigWindow, CW, EventMask, GC

import pytest

from . import Context, xcb

@pytest.fixture
def xcb_conn(request):
    """
    Fixture that will setup and take down a xcffib.Connection object running on
    a display spawned by xvfb
    """
    xvfb = XvfbTest()
    xvfb.setUp()
    request.addfinalizer(xvfb.tearDown)
    return xvfb.conn

def find_root_visual(conn):
    """Find the xcffib.xproto.VISUALTYPE corresponding to the root visual"""
    default_screen = conn.setup.roots[conn.pref_screen]
    for i in default_screen.allowed_depths:
        for v in i.visuals:
            if v.visual_id == default_screen.root_visual:
                return v
    raise AssertionError("Root visual not found")

def create_window(conn, width, height):
    """Creates a window of the given dimensions and returns the XID"""
    wid = conn.generate_id()
    default_screen = conn.setup.roots[conn.pref_screen]

    conn.core.CreateWindowChecked(
        default_screen.root_depth,  # depth
        wid,                        # id
        default_screen.root,        # parent
        0, 0, width, height, 0,     # x, y, w, h, border width
        xcffib.xproto.WindowClass.InputOutput,  # window class
        default_screen.root_visual,             # visual
        CW.BackPixel | CW.EventMask,            # value mask
        [                                       # value list
            default_screen.black_pixel,
            EventMask.Exposure | EventMask.StructureNotify
        ]
    )

    return wid

def create_pixmap(conn, wid, width, height):
    """Creates a window of the given dimensions and returns the XID"""
    pixmap = conn.generate_id()
    default_screen = conn.setup.roots[conn.pref_screen]

    conn.core.CreatePixmapChecked(
        default_screen.root_depth,  # depth
        pixmap, # id
        wid,    # drawable (window)
        width,
        height
    )

    return pixmap

def create_gc(conn):
    """Creates a simple graphics context"""
    gc = conn.generate_id()
    default_screen = conn.setup.roots[conn.pref_screen]

    conn.core.CreateGCChecked(
        gc,                     # id
        default_screen.root,    # drawable
        GC.Foreground | GC.Background,  # value mask
        [                               # value list
            default_screen.black_pixel,
            default_screen.white_pixel
        ]
    )

    return gc

def test_xcb_pixmap(xcb_conn):
    width = 10
    height = 10

    # create a new window
    wid = create_window(xcb_conn, width, height)
    # create the pixmap used to draw with cairo
    pixmap = create_pixmap(xcb_conn, wid, width, height)
    # create graphics context to copy pixmap on window
    gc = create_gc(xcb_conn)

    # create XCB surface on pixmap
    root_visual = find_root_visual(xcb_conn)
    surface = xcb.XCBSurface(xcb_conn, pixmap, root_visual, width, height)
    assert surface

    # use xcb surface to create context, draw white
    ctx = Context(surface)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()

    # map the window and wait for it to appear
    xcb_conn.core.MapWindow(wid)
    xcb_conn.flush()

    start = time.time()
    while time.time() < start + 10:
        event = xcb_conn.wait_for_event()
        if isinstance(event, xcffib.xproto.ExposeEvent):
            break
    else:
        pytest.fail("Never received ExposeEvent")

    # copy the pixmap to the window
    xcb_conn.core.CopyAreaChecked(
        pixmap, # source
        wid,    # dest
        gc,     # gc
        0, 0,   # source x, source y
        0, 0,   # dest x, dest y
        width, height
    )

    xcb_conn.flush()
    # Make sure no errors have been thrown
    ret = True
    while ret:
        ret = xcb_conn.poll_for_event()


def test_xcb_window(xcb_conn):
    width = 10
    height = 10

    # create a new window used to draw with cairo
    wid = create_window(xcb_conn, width, height)

    # create XCB surface on window
    root_visual = find_root_visual(xcb_conn)
    surface = xcb.XCBSurface(xcb_conn, wid, root_visual, width, height)
    assert surface
    # use xcb surface to create context
    ctx = Context(surface)

    # map the window and wait for it to appear
    xcb_conn.core.MapWindow(wid)
    xcb_conn.flush()

    start = time.time()
    while time.time() < start + 10:
        event = xcb_conn.wait_for_event()
        if isinstance(event, xcffib.xproto.ExposeEvent):
            break
    else:
        pytest.fail("Never received ExposeEvent")

    # draw context white
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()

    xcb_conn.flush()
    # Make sure no errors have been thrown
    time.sleep(0.5) # idk, travis is crazy sometimes
    ret = True
    while ret:
        ret = xcb_conn.poll_for_event()

    # now move the window and change its size
    width *= 2
    height *= 2
    xcb_conn.core.ConfigureWindowChecked(
        wid,
        ConfigWindow.X | ConfigWindow.Y | ConfigWindow.Width | ConfigWindow.Height,
        [
            5, 5,           # x, y
            width, height   # width, height
        ]
    )
    xcb_conn.flush()

    # wait for the notification of the size change
    start = time.time()
    while time.time() < start + 10:
        event = xcb_conn.wait_for_event()
        if isinstance(event, xcffib.xproto.ConfigureNotifyEvent):
            break
    else:
        pytest.fail("Never received ConfigureNotifyEvent")

    # re-size and re-draw the surface
    surface.set_size(width, height)
    ctx.paint()

    xcb_conn.flush()
    # Make sure no errors have been thrown
    ret = True
    while ret:
        ret = xcb_conn.poll_for_event()
