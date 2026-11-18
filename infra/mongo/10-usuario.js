// Crea el usuario de los servicios (D28). Lo corre la imagen de mongo con mongosh solo la
// primera vez, con el volumen vacío, igual que postgres/10-inicializa.sh. La contraseña llega
// por el entorno (MONGO_PASSWORD, de infra/.env) y no se escribe en ningún archivo.
const clave = process.env.MONGO_PASSWORD;
if (!clave) {
  throw new Error("Falta MONGO_PASSWORD en infra/.env: corre python infra/genera_env.py");
}
db.getSiblingDB("epidemia").createUser({
  user: "epidemia",
  pwd: clave,
  // epidemia_pruebas es para test_mongo_real.py (MONGO_URL_PRUEBAS): nunca la de la demostración.
  roles: [{ role: "readWrite", db: "epidemia" }, { role: "readWrite", db: "epidemia_pruebas" }],
});
