use std::{
    borrow::Borrow,
    cell::RefCell,
    fmt::Display,
    fs,
    io::Read,
    path::PathBuf,
    rc::Rc,
    str::FromStr,
    sync::{
        atomic::{AtomicBool, AtomicU32, Ordering},
        Arc,
    },
    time,
};

use anyhow::Context;
use tempfile::NamedTempFile;
use wasm_shrink::{IsInteresting, WasmShrink};

use crate::{
    errors::{AResult, CliError},
    meta::{self, Meta},
    Hasheable, Printable, State, NO_WORKERS,
};

#[derive(Debug)]
pub struct Interesting(bool);

impl Display for Interesting {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("")
    }
}

impl IsInteresting for Interesting {
    fn is_interesting(&self) -> bool {
        self.0
    }
}

pub fn reduce_single_binary(state: Arc<State>, chunk: Vec<PathBuf>) -> AResult<()> {
    log::debug!("reducing {} binaries", chunk.len());

    let outfolder = state.out_folder.as_ref().unwrap().clone();
    let dbclient = state.dbclient.as_ref().unwrap().clone();

    'iter: for f in chunk.iter() {
        log::debug!("{:?}", state.finish.load(Ordering::Relaxed));
        if state.finish.load(Ordering::Relaxed) {
            break;
        }
        let mut file = fs::File::open(f)?;

        let name = f.file_name().unwrap().to_str().unwrap().to_string();

        let entry: AResult<Meta> = dbclient.get(&name.clone());

        match entry {
            Err(e) => {
                log::debug!("key not found {}", e);
            }
            Ok(d) => {
                log::debug!("\rSkipping {}", name);
                if state
                    .process
                    .fetch_add(1, std::sync::atomic::Ordering::Acquire)
                    % 100
                    == 99
                {
                    log::debug!("\n{} processed", state.process.load(Ordering::Relaxed));
                }
                continue 'iter;
            }
        }

        // Filter first the header to check for Wasm
        let mut buf = [0; 4];
        let r = &file.read_exact(&mut buf);

        match r {
            Err(e) => {
                log::error!("{}", e);
                continue 'iter;
            }
            Ok(_) => {}
        }

        match &buf {
            // Filter first the header to check for Wasm
            b"\0asm" => {
                let mut meta = meta::Meta::new();
                meta.id = name.clone();
                // Get size of the file
                let fileinfo = fs::metadata(f)?;
                meta.size = fileinfo.len() as usize;

                // Parse Wasm to get more info
                let bindata = fs::read(f)?;
                let cp = bindata.clone();

                let mut reducer = WasmShrink::default();
                let reducer = reducer.attempts(10000);
                //let reducer = reducer.allow_empty(true);

                let output =
                    PathBuf::from_str(&format!("{}/{}.shrunken.wasm", outfolder, name)).unwrap();
                let logs =
                    PathBuf::from_str(&format!("{}/{}.shrunken.logs", outfolder, name)).unwrap();

                // copy the original in the folder to get it as the new shrunked binary

                std::fs::write(output.clone(), bindata.clone()).unwrap();

                log::debug!("Start =========== {}", name);

                let initial_size = cp.len();
                let r = reducer
                    .on_new_smallest(Some(Box::new({
                        let output = output.clone();
                        move |new_smallest: &[u8]| {
                            let tmp = match output.parent() {
                                Some(parent) => NamedTempFile::new_in(parent),
                                None => NamedTempFile::new(),
                            };
                            let tmp = tmp.context("Failed to create a temporary file")?;
                            std::fs::write(tmp.path(), new_smallest).with_context(|| {
                                format!("Failed to write to file: {}", tmp.path().display())
                            })?;
                            std::fs::rename(tmp.path(), &output).with_context(|| {
                                format!(
                                    "Failed to rename {} to {}",
                                    tmp.path().display(),
                                    output.display()
                                )
                            })?;

                            Ok(())
                        }
                    })))
                    .run(cp, move |wasm| Ok(Interesting(wasm.len() > 8)));

                match r {
                    Err(e) => {
                        log::debug!("Error {}", e);
                        if state.save_logs {
                            log::debug!("Saving logs");
                            let name = std::thread::current();
                            let name = name.name().unwrap();
                            let log_file = format!("output{}.log", name);
                            let r = std::fs::rename(log_file, logs.clone());

                            match r {
                                Err(e) => log::error!("{}", e),
                                Ok(_) => {}
                            }
                        }
                        if state
                            .error
                            .fetch_add(1, std::sync::atomic::Ordering::Acquire)
                            % 10
                            == 9
                        {
                            log::error!("{} errors!", state.error.load(Ordering::Relaxed));
                        }
                        continue 'iter;
                    }
                    Ok(_i) => {
                        // Save logs if flag is set
                        if state.save_logs {
                            log::debug!("Saving logs");
                            let name = std::thread::current();
                            let name = name.name().unwrap();
                            let log_file = format!("output{}.log", name);
                            let r = std::fs::rename(log_file, logs.clone());

                            match r {
                                Err(e) => log::error!("{}", e),
                                Ok(_) => {}
                            }
                        }
                    }
                };

                let mut meta = meta::Meta::new();
                meta.id = output.display().to_string();

                let bindata = loop {
                    let bindata = fs::read(output.clone());

                    match bindata {
                        Err(e) => {
                            log::error!("{}", e);
                            continue 'iter;
                        }
                        Ok(r) => break r,
                    }
                };

                // Get size of the file
                meta.tpe = "canonical".to_string();
                meta.hash = bindata.to_vec().hash256().fmt1();
                meta.parent = Some(name.clone());
                meta.size = bindata.len();
                meta.logs = logs.display().to_string();
                meta.description = format!(
                    "seed: {}, fuel: {}, ratio {}",
                    0,
                    1000,
                    bindata.len() as f32 / initial_size as f32
                );

                match dbclient.set(&meta.id.clone(), meta) {
                    Ok(_) => {}
                    Err(e) => {
                        log::error!("{}", e);
                        std::panic::panic_any(e)
                    }
                }
            }
            _ => {
                log::error!("\nJust discard {:?}\n", f);
            }
        }

        if state
            .process
            .fetch_add(1, std::sync::atomic::Ordering::Acquire)
            % 100
            == 99
        {
            log::debug!("{} processed", state.process.load(Ordering::Relaxed));
        }
    }

    Ok(())
}

pub fn reduce_binaries(state: Arc<State>, files: &Vec<PathBuf>) -> Result<(), CliError> {
    let mut workers = vec![vec![]; NO_WORKERS];

    for (idx, file) in files.iter().enumerate() {
        workers[idx % NO_WORKERS].push(file.clone());
    }

    let jobs = workers
        .into_iter()
        .enumerate()
        .map(|(i, x)| {
            let br = state.clone();

            std::thread::Builder::new()
                .name(format!("t{}", i))
                .stack_size(32 * 1024 * 1024 * 1024) // 320 MB
                .spawn(move || reduce_single_binary(br, x))
                .unwrap()
        })
        .collect::<Vec<_>>();

    // Capture ctrl-c signal
    /*
    ctrlc::set_handler(move|| {
        println!("received Ctrl+C! Finishing up");
        t.borrow().finish.store(true,Ordering::SeqCst);
    })
    .expect("Error setting Ctrl-C handler");*/

    for j in jobs {
        let _ = j.join().map_err(|x| CliError::Any(format!("{:#?}", x)))?;
    }

    log::debug!("{} processed", state.process.load(Ordering::Relaxed));
    log::error!(
        "{} parsing errors!",
        state.parsing_error.load(Ordering::Relaxed)
    );
    log::error!("{} errors!", state.error.load(Ordering::Relaxed));

    Ok(())
}

pub fn reduce(state: Arc<State>, path: String) -> AResult<()> {
    log::debug!("Creating folder if it doesn't exist");

    let outf = &state.out_folder;
    let outf = outf.as_ref().unwrap();

    std::fs::create_dir(outf.clone()); // Ignore if error since it's already created

    let mut files = vec![];

    let mut count = 0;
    let mut start = time::Instant::now();

    let meta = fs::metadata(path.clone())?;

    if meta.is_file() {
        files.push(PathBuf::from(path.clone()));
        count += 1;
    } else {
        for entry in fs::read_dir(path)? {
            let entry = entry?;
            let path = entry.path();

            let metadata = entry.metadata()?;

            if !metadata.is_dir() {
                // get files only
                files.push(path);
            }

            if count % 100 == 99 {
                let elapsed = start.elapsed();

                log::debug!("Files count {} in {}ms", count, elapsed.as_millis());
                start = time::Instant::now();
            }

            count += 1;
        }
    }

    log::debug!("Final files count {}", count);
    // Filter files if they are not Wasm binaries
    // Do so in parallel

    reduce_binaries(state, &files)?;
    Ok(())
}
