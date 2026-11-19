"""Services: the business logic, with no knowledge of HTTP.

A service takes plain Python values and returns plain Python values (or
schema objects). It never imports FastAPI, so it can be called from a route,
a background job, a CLI or a test without starting a web server.
"""
