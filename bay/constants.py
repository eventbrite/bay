class PluginHook:
    PRE_BUILD = "pre-build"
    POST_BUILD = "post-build"
    PRE_START = "pre-start"

    valid_hooks = frozenset([PRE_BUILD, POST_BUILD, PRE_START])
