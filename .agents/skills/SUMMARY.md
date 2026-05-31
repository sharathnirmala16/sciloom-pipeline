# DTReg Python Library - Skills Map

This directory contains structured specifications, API contracts, minimal recipes, and common anti-patterns for each module of the `dtreg` library, optimized for **AI Consumption** and automated agents.

## Table of Contents

### Core Interfaces & Logic
- [DTR Interface Protocol & Core Registry Classes](dtr_interface.md) - Duck-typed interface representing the datatype registry protocol, `Epic` and `Orkg` client handlers, and `select_dtr` selection.
- [Load Datatype Resolver](load_datatype.md) - Orchestrator coordinating resolution of datatype schema definitions, prefix binding, property details, and schema validity.
- [JSON-LD Translators](to_jsonld.md) - Core logic translating datasets, custom pandas DataFrames, and structural schemas into standardized, serialized JSON-LD formats.

### Registry Extractors & HTTP Handlers
- [ePIC Extraction Handler](extract_epic.md) - Parsing, processing, and handling nested structures for ePIC schemas.
- [ORKG Extraction Handler](extract_orkg.md) - Direct template metadata parsing, template field extraction, and cardinality conversions for ORKG schemas.
- [Static Configuration Loader](from_static.md) - Parsing schema JSON descriptions directly from the packaged cache directory.
- [HTTP/API Request Client](request_dtr.md) - Low-level HTTP request client with query routing, headers, and mock support.

### Utilities
- [Helper Functions & Formatting](helpers.md) - Lower-level utility helpers including prefix extraction, cardinality parsing, safe string formatting, and ID generator factory.
