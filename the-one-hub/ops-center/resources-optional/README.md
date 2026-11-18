# Opt-in resources

Not deployed. `databricks.yml` includes `resources/*.yml` only.

## schemas.yml

Seven schemas, one per store, with the leads zone firewalled by grant rather
than by naming convention. That is the cleaner model and it is what the
blueprint describes.

It needs `CREATE SCHEMA` on the catalog. A new user in a governed workspace
usually does not have that, which is why it is not the default: a bundle that
cannot deploy teaches nothing.

To use it:

```powershell
Copy-Item resources-optional\schemas.yml resources\
.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle -Catalog <yours> -Schema <ignored> -Execute
```

With schemas deployed, set `-StorePrefix ""` and point `-Schema` at the
`serving` schema, since each store then has a schema of its own.
