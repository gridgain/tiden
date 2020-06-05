Integration to slack plugin
=============================

This plugin push result of tests run to slack

Example configuration
---------------------
To use this plugin, put following section into your environment YAML.

```
plugins:
  SlackPlugin:
    print_results:
    direct_message:
    direct_name:
    bot_name:
    slack_token:
```

where
    print_results: True / False and turns print to channel/user accordingly to this value
    direct_message: channel / user
    direct_name: name (without @) of channel (public / private - token user need to have access this channels)
    bot_name: by default it TidenSlackBot
    slack_token: API token to connect slack - generate here - https://api.slack.com/custom-integrations/legacy-tokens


