Environment variables extrapolation
===================================

This plugin enables shell environment variables extrapolation in Tiden YAML config files.

Otherwise speaking, it replaces placeholder expressions found in config to corresponding values.

All replacement is done locally before any other plugins and before tests run.

Allowed placeholder formats
---------------------------

```
    1. ${VAR_NAME}
    2. $VAR_NAME
    3. ${VAR_NAME:-default}
    4. ${VAR_NAME:default}
```

For variant 1. and 2. placeholder will be replaced to the value of shell environment variable `VAR_NAME` 
if it is defined. If variable is undefined, no replacement is made and a warning would be printed.

For variant 3. placeholder will be replaced to the value of shell environment variable `VAR_NAME` 
if it is defined. However, if variable is undefined, it will be replaced to the `default` value 
and no warning would be printed in that case. 

Example configuration
---------------------
To use this plugin, put following section into your environment YAML.

```
plugins:
  EnvExpander:
```

Ignoring specific variables
---------------------------

As some section of configs may have values that are actual shell code and don't need to be replaced locally 
(e.g. `env_vars` section), you may instruct `EnvExpander` to ignore some placeholders.

```
plugins:
  EnvExpander:
    ignore_vars:
      - <not_extrapolated_var_name>
```

Here, placeholder `${not_extrapolated_var_name}` will be left unchanged in config.

Of course, in that case no warning would be printed if `not_extrapolated_var_name` is undefined locally. 


Computing variables values
--------------------------
You may want to replace some placeholder to the value, computed on the fly depending
on other variables or config values. 

```
plugins:
  EnvExpander:
    compute_vars: 
      <computed_var_name>: '<python expression>'
```

Here, `$computed_var_name` will be replaced to the evaluated value of `python expression`.

More practical example:
```
plugins:
  EnvExpander:
    compute_vars: 
      GRIDGAIN_VERSION: 'e.get("IGNITE_VERSION", "").replace("2.", "8.", 1)'
```

Here, `e` is a shortcut to current environment at the time of python expression evaluation, 
and `$GRIDGAIN_VERSION` will be replaced to the value if `IGNITE_VERSION` shell variable with first `'2.'` replaced to `'8.'`.

You may also use `c` shortcut to get current Tiden config at the time of python expression evaluation.

```
plugins:
  EnvExpander:
    compute_vars: 
      SERVERS_COUNT: 'len(c["environment"]["server_hosts"])'
```

Here `$SERVERS_COUNT` will be replaced to the number of hosts in `environment.server_hosts` config section.

Expanding variables lists
-------------------------
Last feature of the plugin is to expand some config sections into multiple sections corresponding 
to each value from the comma-separated list found in given environment variable.

```
plugins:
  EnvExpander:
    expand_vars: 
      - <expanded_var_name>
      
```

Better to understand this feature by example. 

Given following config section:

```
plugins:
  EnvExpander:
    expand_vars: [SOURCE, VERSION] 

artifacts:
    ${SOURCE}-${VERSION}:
        type: ignite
        glob_path: 'ftp://somewhere.net/releases/${SOURCE}-${VERSION}.zip'
```

and following values for environment shell variables:
```
export SOURCE=apache-ignite,gridgain-community
export VERSION=2.5.0,2.6.0
```

Following configuration will be generated by the plugin for the tests:

```
artifacts:
    apache-ignite-2.5.0:
        type: ignite
        glob_path: ftp://somewhere.net/releases/apache-ignite-2.5.0.zip
    apache-ignite-2.6.0:
        type: ignite
        glob_path: ftp://somewhere.net/releases/apache-ignite-2.6.0.zip
    gridgain-community-2.5.0:
        type: ignite
        glob_path: ftp://somewhere.net/releases/gridgain-community-2.5.0.zip
    gridgain-community-2.6.0:
        type: ignite
        glob_path: ftp://somewhere.net/releases/gridgain-community-2.6.0.zip
```
