class PluginHook:
    PRE_BUILD = "pre-build"
    POST_BUILD = "post-build"
    PRE_START = "pre-start"
    POST_START = "post-start"
    DOCKER_FAILURE = "docker-fail"

    valid_hooks = frozenset([
        PRE_BUILD,
        POST_BUILD,
        PRE_START,
        POST_START,
        DOCKER_FAILURE,
    ])
