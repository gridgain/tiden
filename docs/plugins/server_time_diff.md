Servers local time differences
==============================

This plugin checks if all servers given to Tiden have local time synchronized and optionally bails out if it is not.


Example configuration
---------------------
To use this plugin, put following section into your environment YAML.

```
plugins:
  ServerTimeDiff:
    acceptable_time_diff: 1000
```

where
    acceptable_time_diff: (milliseconds, default 1000) difference in local servers time considered acceptable to not fail the test session.


