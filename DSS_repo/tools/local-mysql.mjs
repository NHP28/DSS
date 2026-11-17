// Optional Windows helper: existing MySQL binaries, isolated data directory and loopback port.
// Never touches another MySQL installation's data or Windows services.
import {spawn,spawnSync} from 'node:child_process';
import {existsSync,mkdirSync,readdirSync,readFileSync,writeFileSync,openSync,closeSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';
import mysql from 'mysql2/promise';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const runtime=resolve(root,'.runtime');
const data=resolve(runtime,'mysql-data');
const adminFile=resolve(runtime,'mysql-admin.json');
const action=process.argv[2]||'status';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const connect=password=>mysql.createConnection({host:'127.0.0.1',port:3307,user:'root',password,connectTimeout:2000});
async function main(){
  if(!['start','stop','status'].includes(action))throw new Error('Usage: node tools/local-mysql.mjs start|stop|status');
  mkdirSync(runtime,{recursive:true});
  const admin=existsSync(adminFile)?JSON.parse(readFileSync(adminFile,'utf8')):null;
  if(admin){
    try{
      const db=await connect(admin.password);
      if(action==='stop'){
        await db.query('SHUTDOWN');
        await db.end();
        // Wait for the listener to disappear before a subsequent start command.
        for(let attempt=0;attempt<100;attempt++){
          try{const probe=await connect(admin.password);await probe.end();await sleep(200);}
          catch(error){if(['ECONNREFUSED','ECONNRESET','PROTOCOL_CONNECTION_LOST'].includes(error.code))break;throw error;}
        }
        console.log('Stopped workspace MySQL (3307).');return;
      }
      else console.log('Workspace MySQL is ready on 127.0.0.1:3307.');
      await db.end();return;
    }catch(error){
      if(!['ECONNREFUSED','ETIMEDOUT','ECONNRESET','PROTOCOL_CONNECTION_LOST'].includes(error.code))throw error;
      if(action!=='start'){console.log('Workspace MySQL is stopped.');return;}
    }
  }else if(action!=='start'){console.log('Workspace MySQL has not been initialized.');return;}
  if(process.platform!=='win32')throw new Error('Use docker compose on this OS, or configure an existing MySQL instance.');
  const found=spawnSync('where.exe',['mysqld.exe'],{encoding:'utf8',windowsHide:true});
  const binary=process.env.MYSQLD_PATH||found.stdout?.trim().split(/\r?\n/)[0];
  if(!binary||!existsSync(binary))throw new Error('mysqld.exe not found. Set MYSQLD_PATH or use Docker Compose.');
  const base=dirname(dirname(binary));
  mkdirSync(data,{recursive:true});
  const common=['--no-defaults',`--basedir=${base}`,`--datadir=${data}`];
  if(!existsSync(resolve(data,'auto.cnf'))){
    if(readdirSync(data).length)throw new Error('Refusing to initialize a nonempty data directory.');
    const init=spawnSync(binary,[...common,'--initialize-insecure','--console'],{windowsHide:true,encoding:'utf8'});
    if(init.status!==0)throw new Error(init.stderr||'MySQL initialization failed');
  }else if(!admin)throw new Error('Existing workspace data has no admin file. Configure access manually.');
  const log=openSync(resolve(runtime,'mysql.log'),'a');
  const child=spawn(binary,[...common,'--bind-address=127.0.0.1','--port=3307','--mysqlx=0','--console'],{detached:true,windowsHide:true,stdio:['ignore',log,log]});
  child.unref();closeSync(log);
  let connection;
  for(let attempt=0;attempt<50;attempt++){
    try{connection=await connect(admin?.password);break;}catch(error){if(attempt===49)throw error;await sleep(200);}
  }
  if(!connection)throw new Error('MySQL startup failed; see .runtime/mysql.log');
  if(!admin){
    const password=randomBytes(24).toString('hex');
    await connection.query('CREATE DATABASE danang_dss CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');
    await connection.query("CREATE USER 'dss'@'127.0.0.1' IDENTIFIED BY ?",['dss_local_password']);
    await connection.query("GRANT ALL PRIVILEGES ON danang_dss.* TO 'dss'@'127.0.0.1'");
    await connection.query("ALTER USER 'root'@'localhost' IDENTIFIED BY ?",[password]);
    writeFileSync(adminFile,JSON.stringify({port:3307,password}));
  }
  await connection.end();
  const envFile=resolve(root,'apps/api/.env');
  if(!existsSync(envFile))writeFileSync(envFile,readFileSync(resolve(root,'apps/api/.env.example'),'utf8').replace('DB_PORT=3306','DB_PORT=3307'));
  console.log('Started workspace MySQL on 127.0.0.1:3307. Local API .env is ready.');
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
