Zabbix metrics collector plugin
===============================

This plugin collects miscellaneous metrics from Zabbix during test, and optionally build graph.


Example configuration
---------------------

```
plugins:
  Zabbix:
    url: 'https://<zabbix_url/'
    login: '<login>'
    password: '<password>'
    metrics:
      - 'Available memory'
      - 'The time the CPU has spent doing nothing'
    create_plot: true 
```
