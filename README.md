# Apple Photos to Piwigo Sync

## Setup

```
python3 -m venv piwigo-sync
source piwigo-sync/bin/activate
pip install -r requirements3.txt
```

## Run

```
./sync.py
```

## Compatibility

Should be compatible with modern versions of OSX that support the [osxphotos](https://pypi.org/project/osxphotos/) pypi package.

Tested versions include:

 * macOS 10.15.7 with Apple Photos 5.0 ( @trainman419 )

If you test on a different version and find that tool works, please submit a PR adding your version number to this list.
