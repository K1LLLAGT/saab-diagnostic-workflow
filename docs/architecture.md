# SAAB-SUITE Architecture

This document shows how the pieces fit together: hardware, VM, OEM tools, and SAAB-SUITE scripts.

---

## High-level diagram

```text
+-----------------------------+
|        Technician           |
+--------------+--------------+
               |
               v
+-----------------------------+
|        SAAB CLI (./saab)    |
|  - workflow                 |
|  - quick-scan               |
|  - doctor                   |
+--------------+--------------+
               |
               v
+-----------------------------+
|       SAAB-SUITE Scripts    |
|  - scripts/saab-diagnostic- |
|    workflow.sh              |
|  - scripts/saab-quick-scan.sh|
|  - src/* (CAN, UDS, J2534)  |
+--------------+--------------+
               |
               v
+-----------------------------+
|      Win7-SAAB VM           |
|  - GlobalTIS SPS            |
|  - GDS2                     |
|  - TIS2000                  |
|  - J2534 Toolbox 3          |
+--------------+--------------+
               |
               v
+-----------------------------+
|   Mongoose Pro GM II (USB)  |
+--------------+--------------+
               |
               v
+-----------------------------+
|       SAAB Vehicle (OBD-II) |
+-----------------------------+
```
