# Dentists and collaborators

The professionals module keeps a clinic directory for dentists and other
collaborators. Each profile can contain a photo URL, specialty, professional
license, contact details, notes and active state.

It is separate from user accounts: a collaborator does not need a login to be
recorded. The directory is available at `/professionals` to users with
`professionals.read`; profile administration requires `professionals.write`.
