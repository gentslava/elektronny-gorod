# Sanitized mobile-app 9.9.0 contracts

These fixtures preserve response shapes observed in decrypted runtime traffic
without retaining live account data. They are implementation inputs for the
mobile-app parity plan, not verbatim HAR exports.

| Fixture | Runtime evidence represented |
|---|---|
| `guest_invite_success.json` | owner-side NTK guest-link response |
| `guest_invite_unauthorized.json` | same POST without authorization: HTTP 401 and non-JSON text |
| `events_search_page_0.json` | accepted and missed intercom-call event DTOs |
| `events_search_pagination.json` | page 0/1/2 metadata plus repeated page-0 overlap |
| `camera_motion_event.json` | forpost motion/archive event DTO |
| `video_retention_11005.json` | archive-out-of-range business error returned with HTTP 500 |

All IDs, timestamps, messages and URLs are synthetic. The guest link is an
`example.invalid` sentinel. Tests must never replace these values with data
copied from local HAR files.

The observed history sequence was `0 → 1 → 2 → 0`. Adjacent pages shared no
IDs, while the repeated page 0 shared all 20 IDs with the first poll. The
backend reported `totalElements` as `21 → 41 → 61 → 21`, so these totals are
lower-bound pagination hints rather than a stable count.
