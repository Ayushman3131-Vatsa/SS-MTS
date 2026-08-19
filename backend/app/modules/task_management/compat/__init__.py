"""Compatibility boundary for the pre-existing project and task APIs.

The public legacy routers keep their historical import paths. Their services are
thin translators into this offering package so old clients and new clients share
the same authorization, workflow, transaction, and audit implementation.
"""
