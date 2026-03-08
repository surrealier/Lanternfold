# MVP Spec

## Product Goal

Turn detected video events into operator-ready decisions with evidence, policy grounding, and notifications.

## Included

- Upload a video source or register an RTSP source.
- Run deterministic inference to create logical events and evidence.
- Upload policy documents and chunk them for retrieval.
- Generate an operator report with summary, risk, policy references, actions, trace, and notification.
- Ask grounded operator questions about an event.
- Review results in a simple dashboard.

## Excluded

- Real-time multi-camera scale-out
- Production auth/RBAC
- Multi-agent collaboration
- Graph store
- Advanced UI polish

## Acceptance Slice

1. Upload a markdown SOP.
2. Upload a sample MP4 named with an event keyword such as `fall_demo.mp4`.
3. Create an inference job.
4. Observe a structured event.
5. Generate a report.
6. Ask why the event is high risk.
7. View the event and report in the dashboard.