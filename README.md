# pylogmet

[![Build Status](https://travis-ci.org/locke105/pylogmet.svg?branch=master)](https://travis-ci.org/locke105/pylogmet)
[![Apache License](http://img.shields.io/badge/license-APACHE2-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0.html)

A Pythonic Logmet client

# usage

```python
import logmet

lm = logmet.Logmet(
    logmet_host='metrics.opvis.bluemix.net',
    logmet_port=9095,
    space_id='deadbbeef1234567890',
    token='put_your_logmet_logging_token_here'
)

lm.emit_metric(name='logmet.test.1', value=1)
lm.emit_metric(name='logmet.test.2', value=2)
lm.emit_metric(name='logmet.test.3', value=3)
```

# Where do I find my token?

Find your logging token and space ID by running `python get_token.py` and
following the prompts.
