Test Results Collector Plugin
=============================

This plugin can collect test results (e.g. any test output files) from remote client/server hosts. 

Results can be collected either once per session, once per test class, or per each test method.

Plugin works in two steps: first executes remote commands (to zip result files), then downloads archive
files by given masks. Optionally, plugin can unpack collected archives.  

Example configuration
---------------------
To use this plugin, put following section into your environment YAML.

```
plugins:
    TestResultsCollector:
        scope: <scope>
        remote_commands:
          - <command>
        download_masks:
          - <mask>
        unpack_logs: <unpack>
```

Where `scope` (optional) is one of:
- `method` - collect results after each test method complete
- `class` - collect results after each test class complete
- `session` - collect results after all test session complete

Default value for `scope` is: `method`        

And `command` (optional) is a command to execute remotely to create archives.

Default value for `remote_commands` is:
   
    "zip --symlinks -r _logs.zip -i {include_mask} -x {exclude_mask}"


And `mask` (optional) is a shell glob mask for remote files to collect.

Default value for `download_masks` is: "_logs.zip"

And `unpack_logs` (optional) is whether to unpack collected archives or not.
Default: False 

If default values are ok for you but for few options, you can as well pass them to run-tests.py via --to argument.

Example:
    run-tests.py  --ts=<mysuite> --tc=config/env_my.yaml --to=plugins.TestResultsCollector.unpack_logs=true
