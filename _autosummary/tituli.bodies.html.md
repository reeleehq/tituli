# tituli.bodies

A lacing body schema for a rendered caption (`pip install tituli[lacing]`).

URI: `annot://schema/text-overlay/v1`. A caption is an annotation \*\*on the
image\*\* (`MediaRef(asset_id=<image hash>)`), and when that image sits under an
audio segment the pair is expressed the way `artful.PanelBody` does it: the
annotation’s `reference` is the interval on the segment and
`provenance.was_derived_from` lists both the image `asset_id` and the
caption annotation id. No N-ary reference type is invented; the timing lives
on the reference, not in this body.

Registration is lazy and idempotent ([`register()`](#tituli.bodies.register)), so `import tituli`
never touches lacing.

### Functions

| [`register`](#tituli.bodies.register)()                               | Register the schema with lacing (once).                             |
|-------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| [`body_for`](#tituli.bodies.body_for)(layout, frame, \*, text[, ...]) | The body dict for a rendered layout — plain data, no lacing needed. |

### tituli.bodies.body_for(layout, frame, , text, attribution='', kind='caption', unlabelled=False)

The body dict for a rendered layout — plain data, no lacing needed.

```pycon
>>> from tituli.frame import Frame
>>> from tituli.compose import caption
>>> f = Frame.blank((1920, 1080))
>>> b = body_for(caption("A still", "PD", frame=f), f, text="A still", attribution="PD")
>>> b["kind"], b["anchor"], len(b["box"])
('caption', 'bottom-left', 4)
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### tituli.bodies.register()

Register the schema with lacing (once). Returns the URI.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
