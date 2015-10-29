# coding=utf-8

from subzero import intent
from subzero.constants import TITLE, ART, ICON, PREFIX, PLUGIN_IDENTIFIER
from support.config import config
from support.helpers import pad_title, encode_message, decode_message
from support.auth import refresh_plex_token
from support.storage import resetStorage
from support.items import getRecentlyAddedItems, getOnDeckItems, refreshItem
from support.missing_subtitles import searchAllRecentlyAddedMissing
from support.background import scheduler

# init GUI
ObjectContainer.title1 = TITLE
ObjectContainer.art = R(ART)
ObjectContainer.no_history = True
ObjectContainer.no_cache = True

@handler(PREFIX, TITLE, art=ART, thumb=ICON)
def fatality():
    """
    subzero main menu
    """
    oc = ObjectContainer(no_cache=True, no_history=True)
    oc.add(DirectoryObject(
        key=Callback(OnDeckMenu),
        title="Subtitles for 'On Deck' items",
	summary="Shows the current on deck items and allows you to individually (force-) refresh their metadata/subtitles."
    ))
    oc.add(DirectoryObject(
        key=Callback(RecentlyAddedMenu),
        title="Subtitles for 'Recently Added' items (max-age: %s)" % Prefs["scheduler.item_is_recent_age"],
	summary="Shows the recently added items, honoring the configured 'Item age to be considered recent'-setting (%s) and allowing you to individually (force-) refresh their metadata/subtitles." % Prefs["scheduler.item_is_recent_age"]
    ))
    oc.add(DirectoryObject(
        key=Callback(RefreshMissing),
        title="Refresh all (recently added) items with missing subtitles (max-age: %s)" % Prefs["scheduler.item_is_recent_age"],
	summary="Automatically run periodically by the scheduler, if configured. Last scheduler run: %s; Next scheduled run: %s" % (scheduler.last_run("searchAllRecentlyAddedMissing") or "never", scheduler.next_run("searchAllRecentlyAddedMissing") or "never")
    ))
    oc.add(DirectoryObject(
        key=Callback(AdvancedMenu),
        title="Advanced functions",
	summary="Use at your own risk"
    ))

    return oc



@route(PREFIX + '/on_deck')
def OnDeckMenu(message=None):
    return mergedItemsMenu(title="Items On Deck", itemGetter=getOnDeckItems)

@route(PREFIX + '/recent')
def RecentlyAddedMenu(message=None):
    return mergedItemsMenu(title="Recently Added Items", itemGetter=getRecentlyAddedItems)

def mergedItemsMenu(title, itemGetter):
    oc = ObjectContainer(title2=title, no_cache=True, no_history=True)
    items = itemGetter()

    for kind, title, item in items:
	menu_title = title
	oc.add(DirectoryObject(
    	    key=Callback(RefreshItemMenu, title=menu_title, rating_key=item.rating_key),
    	    title=menu_title
	))

    return oc

@route(PREFIX + '/item/{rating_key}/actions')
def RefreshItemMenu(rating_key, title=None, came_from="/recent"):
    oc = ObjectContainer(title1=title, no_cache=True, no_history=True)
    oc.add(DirectoryObject(
    	key=Callback(RefreshItem, rating_key=rating_key),
    	title=u"Refresh: %s" % title,
	summary="Refreshes the item, possibly picking up new subtitles on disk"
    ))
    oc.add(DirectoryObject(
    	key=Callback(RefreshItem, rating_key=rating_key),
    	title=u"Force-Refresh: %s" % title,
	summary="Issues a forced refresh, ignoring known subtitles and searching for new ones"
    ))

    return oc


@route(PREFIX + '/item/{rating_key}')
def RefreshItem(rating_key=None, came_from="/recent", force=False):
    assert rating_key
    Thread.Create(refreshItem, rating_key=rating_key, force=force)
    return ObjectContainer(message="%s of item %s triggered" % ("Refresh" if not force else "Forced-refresh", rating_key))

@route(PREFIX + '/missing/refresh')
def RefreshMissing():
    Thread.CreateTimer(1.0, searchAllRecentlyAddedMissing)
    return ObjectContainer(message="Refresh of recently added items with missing subtitles triggered")

@route(PREFIX + '/advanced')
def AdvancedMenu():
    oc = ObjectContainer(header="Internal stuff, pay attention!", no_cache=True, no_history=True, title2="Advanced")
    
    oc.add(DirectoryObject(
        key=Callback(TriggerRestart),
        title=pad_title("Restart the plugin")
    ))
    oc.add(DirectoryObject(
        key=Callback(RefreshToken),
        title=pad_title("Re-request the API token from plex.tv")
    ))
    oc.add(DirectoryObject(
        key=Callback(ResetStorage, key="subs"),
        title=pad_title("Reset the plugin's internal subtitle information storage")
    ))
    return oc

@route(PREFIX + '/ValidatePrefs')
def ValidatePrefs():
    Log.Debug("Validate Prefs called.")
    config.initialize()
    scheduler.discover_tasks()
    return

@route(PREFIX + '/advanced/restart/trigger')
def TriggerRestart():
    Thread.CreateTimer(1.0, Restart)
    return ObjectContainer(message="Restart triggered, please wait about 5 seconds")

@route(PREFIX + '/advanced/restart/execute')
def Restart():
    config.Plex[":/plugins"].restart(PLUGIN_IDENTIFIER)

@route(PREFIX + '/storage/reset', sure=bool)
def ResetStorage(key, sure=False):
    if not sure:
	oc = ObjectContainer(no_history=True, title1="Reset subtitle storage", title2="Are you sure?")
	oc.add(DirectoryObject(
	    key=Callback(ResetStorage, key=key, sure=True),
	    title=pad_title("Are you really sure? The internal subtitle storage is very useful!")
	))
	return oc

    resetStorage(key)
    return ObjectContainer(
        header='Success',
        message='Subtitle Information Storage reset'
    )

@route(PREFIX + '/refresh_token')
def RefreshToken():
    result = refresh_plex_token()
    if result:
	msg = "Token successfully refreshed."
    else:
	msg = "Couldn't refresh the token, please check your credentials"
    
    return ObjectContainer(message=msg)
