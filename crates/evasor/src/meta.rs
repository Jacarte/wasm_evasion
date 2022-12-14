//! DTO for analysis tool

use bitflags::bitflags;
use std::{collections::HashMap, hash::Hash, ops::Range};

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct MutationMap {
    /// Code section where the target is located
    pub section: u8,

    /// True if the target element belongs to an index, e.g. fidx
    pub is_indexed: bool,

    /// Index of the element, if indexed, otherwise its offset in the binary
    #[serde(skip_serializing)]
    #[serde(default)]
    pub idx: Vec<u8>,

    /// Natural description of how the mutation can be applide, e.g. for the custom, if it is the name or the data part
    pub how: String,

    /// Count (if possible) of the number of possible mutations depending on how (-1 for infinite)
    pub many: i64,

    /// Display of the target, None if it is not relevant
    pub display: Option<String>,
    /// Map for arbitrary metadata information
    pub meta: Option<HashMap<String, String>>,
}

bitflags! {

    pub struct MutationType: u8 {
        const Add = 0x01;
        const Edit = 0x02;
        const Delete = 0x04;
    }
}

impl MutationType {
    pub fn get_val(&self) -> u8 {
        self.bits
    }
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct MutationInfo {
    pub class_name: String,
    pub pretty_name: String,
    pub desccription: String,
    pub map: (usize, String),
    pub generic_map: Option<HashMap<String, Vec<MutationMap>>>,
    pub can_reduce: bool,
    pub affects_execution: bool,
    pub tpe: u8,
    #[serde(default)]
    pub sampled: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Meta {
    pub id: String,
    pub size: usize,
    pub tpe: String,
    pub hash: String,
    pub parent: Option<String>,
    pub description: String,
    pub logs: String,

    // Static info
    pub tpe_section: Option<Range<usize>>,
    pub import_section: Option<Range<usize>>,
    pub export_section: Option<Range<usize>>,
    pub function_count: u32,
    pub table_section: Option<Range<usize>>,
    pub memory_count: u32,
    pub global_section: Option<Range<usize>>,
    pub start_section: Option<Range<usize>>,
    pub element_section: Option<Range<usize>>,
    pub data_section: Option<Range<usize>>,
    pub unknown_section: Option<Range<usize>>,
    pub version: u32,
    pub tag_section: Option<Range<usize>>,
    // Add here some counters
    // Number of functions, number of globals, number of data sections, number of tags, number of elements, number of exports, number of types, number of tables
    #[serde(default)]
    pub num_tpes: u32,
    #[serde(default)]
    pub num_imports: u32,
    #[serde(default)]
    pub num_exports: u32,
    #[serde(default)]
    pub num_tables: u32,
    #[serde(default)]
    pub num_globals: u32,
    #[serde(default)]
    pub num_elements: u32,
    #[serde(default)]
    pub num_data: u32,
    #[serde(default)]
    pub num_data_segments: u32,
    #[serde(default)]
    pub num_tags: u32,
    // custom data info
    pub custom_sections: HashMap<String, (u32, u32)>,
    pub custom_sections_count: u32,

    // code data aggregation
    pub num_instructions: u32,

    // mutation info
    pub mutations: Vec<MutationInfo>,
}

impl Meta {
    pub fn new() -> Meta {
        Meta {
            id: "unset".to_string(),
            size: 0,
            tpe: "original".to_string(),
            hash: "".to_string(),
            description: "".to_string(),
            logs: "".to_string(),

            tpe_section: None,
            parent: None,
            import_section: None,
            export_section: None,
            function_count: 0,
            table_section: None,
            memory_count: 0,
            global_section: None,
            start_section: None,
            element_section: None,
            data_section: None,
            unknown_section: None,
            version: 1,
            tag_section: None,

            custom_sections: HashMap::new(),

            custom_sections_count: 0,
            num_instructions: 0,
            mutations: vec![],
            num_tpes: 0,
            num_imports: 0,
            num_exports: 0,
            num_tables: 0,
            num_globals: 0,
            num_elements: 0,
            num_data: 0,
            num_data_segments: 0,
            num_tags: 0,
        }
    }
}
