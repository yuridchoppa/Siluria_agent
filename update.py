import re
import os

with open('requirements.txt', 'r') as f:
    reqs = f.read()
reqs = reqs.replace('google-genai>=0.1.0', 'openai>=1.14.0')
with open('requirements.txt', 'w') as f:
    f.write(reqs)

with open('pyproject.toml', 'r') as f:
    toml = f.read()
toml = toml.replace('"google-genai>=0.1.0"', '"openai>=1.14.0"')
with open('pyproject.toml', 'w') as f:
    f.write(toml)
