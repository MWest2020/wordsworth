# Design

Export unwraps each key inside the service and re-wraps it for the receiving
key in one step; clear material exists only in the service's memory for that
step. The bundle carries no clear key. An export without a receiving key, with
a malformed key, or for a domain the caller may not administer is refused
before anything is unwrapped.
