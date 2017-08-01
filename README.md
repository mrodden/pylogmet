# pylogmet

[![Build Status](https://travis-ci.org/locke105/pylogmet.svg?branch=master)](https://travis-ci.org/locke105/pylogmet)
[![Apache License](http://img.shields.io/badge/license-APACHE2-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0.html)

A Pythonic Logmet client

# usage

## Sending metrics
```python
import logmet

lm = logmet.Logmet(
    logmet_host='metrics.opvis.bluemix.net',
    logmet_port=9095,
    space_id='deadbeef1234567890',
    token='put_your_logmet_logging_token_here'
)

lm.emit_metric(name='logmet.test.1', value=1)
lm.emit_metric(name='logmet.test.2', value=2)
lm.emit_metric(name='logmet.test.3', value=3)
```

## Sending logs
```python
import logmet

lm = logmet.Logmet(
    logmet_host='logs.opvis.bluemix.net',
    logmet_port=9091,
    space_id='deadbeef1234567890',
    token='put_your_logmet_logging_token_here'
)

# Emitting a string will map the string to the "message" field in Logmet Kibana
lm.emit_log('This is a log message')

# You can also emit a dictionary with additional fields.
# These can be searched and filtered on in Logmet Kibana.
lm.emit_log(
    {'app_name': 'myApp',
     'type': 'myType',
     'message': 'This is a log message'}
)
```

# Where do I find my token?

Find your logging token and space ID by running `python get_token.py` and
following the prompts. If you log into Bluemix using an SSO, use `apikey`
as your username and a [Bluemix API Key](https://console.bluemix.net/iam/#/apikeys)
as the password, when prompted.
