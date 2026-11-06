# Design: particle-names-measured

Carried over from `detect-dutch-particle-names`:

- **Opt-in layer, defaults unchanged.** Existing runs stay comparable.
- **The second PERSON number is full-pipeline recall** with the `per_layer`
  breakdown, on names whose first names are not in the gazetteer's source;
  the `dutch_particle_name` layer's own number is not presented as recall
  (near zero by construction on such a set).
- **Circular measurement, said so.** The gold names come from
  `eval/synthetic.py`, the gazetteer's own source.
- **Unknown recall, said so.** Document `1c87f856` is not re-run here; the
  Gooise Meren miss is not claimed closed.
- **No service, no number.** If OpenAnonymiser is unreachable, the run records
  "not run".
