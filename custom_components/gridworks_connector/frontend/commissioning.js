/* Local HA admin UI. All edits use HA's authenticated options-flow API. */
const DOMAIN = "gridworks_connector";
const FLOW = "config/config_entries/options/flow";
const labels = {
  entity_id: "Home Assistant entity", attribute: "Attribute (optional)", label: "Label",
  unit: "Unit of measurement", lower: "Lower temperature limit", upper: "Upper temperature limit",
  stale_seconds: "Mark stale after (seconds)", kind: "Observation type", meter_id: "Meter ID",
  mode_id: "Mode ID", service_id: "Service ID", coverage: "What this meter measures",
  provenance: "Meter provenance (optional)", parent_meter_id: "Parent meter (optional)",
  state_value: "Corresponding local mode state (optional)", availability: "Declared availability",
  delivery_feedback: "Delivery feedback is available", address: "Address", latitude: "Latitude",
  longitude: "Longitude", mode: "Shadow peer", host: "Broker host", port: "Broker port",
  tls: "Use TLS", send_topic: "Send topic", receive_topic: "Receive topic", username: "Username",
  ca_path: "Trusted CA file path", cert_path: "Client certificate file path",
  key_path: "Private key file path", test_endpoint_confirmed: "This is an approved test-only endpoint",
  primary_source: "Primary weather source", backup_sources: "Backup sources",
  confirmed: "I confirm these sources represent the site"
};
const titles = {temperature: "Thermal State Channel", signal: "Observation", mode: "Operating Mode",
  meter: "Electric Meter", service: "Thermal Service", site: "Site Location",
  transport: "Shadow Peer", broker: "Approved Test Broker", weather: "Weather Sources", finish: "Configuration incomplete"};
const help = {temperature: "Select an existing entity or its temperature attribute. Both limits must use the selected unit.",
  signal: "Select an existing entity and state what it actually measures. Missing feedback stays unknown.",
  mode: "Define a discrete operating configuration. This does not operate equipment.",
  meter: "Define the measurement boundary, then add its power or energy observation using the other button in Electric Meters.",
  service: "A thermostat call is a service request; it does not prove that heat was delivered.",
  weather: "The embedded catalog is a test. Confirming this form immediately sends the selection to the shadow peer.",
  broker: "Use credentials and routes approved for this test. Private key paths refer to protected files on Home Assistant.",
  finish: "Add at least one temperature channel with valid limits and complete any selected external connection fields."};
const human = value => String(value).replaceAll("_", " ").replace(/^./, c => c.toUpperCase());
function node(tag, props = {}, children = []) {
  const item = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith("on")) item.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === "text") item.textContent = value;
    else if (key.startsWith("aria-")) item.setAttribute(key, value);
    else item[key] = value;
  }
  item.append(...children);
  return item;
}
const style = `
:host{display:block;height:100%;overflow:auto;background:var(--primary-background-color,#fafafa);color:var(--primary-text-color,#212121);font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif)}
*{box-sizing:border-box}main{max-width:1200px;margin:auto;padding:24px 24px 100px}header{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:12px}h1{font-size:27px;font-weight:500;margin:0;flex:1}h2{font-size:21px;font-weight:500;margin:0}p{line-height:1.5}.intro{color:var(--secondary-text-color,#666);margin:12px 0 20px}.status{border-left:4px solid var(--primary-color,#03a9f4);padding:12px 16px;background:var(--card-background-color,white);margin-bottom:20px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;align-items:start}.card{border:1px solid var(--divider-color,#ddd);border-radius:14px;padding:22px;background:var(--card-background-color,white)}.explanation{color:var(--secondary-text-color,#666);margin:12px 0 16px;font-size:14px}.empty{font-style:italic;color:var(--secondary-text-color,#666);padding:12px 0}.entry{padding:14px 0;border-top:1px solid var(--divider-color,#ddd)}.entry-name{font-weight:600}.source,.detail{font-size:13px;color:var(--secondary-text-color,#666);overflow-wrap:anywhere;margin-top:5px}.actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.entry .actions{margin-top:9px}button{font:inherit;cursor:pointer;border:1px solid var(--primary-color,#03a9f4);border-radius:20px;padding:9px 15px;background:transparent;color:var(--primary-color,#0288d1);min-height:40px}button:hover{background:color-mix(in srgb,var(--primary-color,#03a9f4) 9%,transparent)}button:disabled{opacity:.45;cursor:default}.small{font-size:13px;min-height:32px;padding:5px 11px}.primary{background:var(--primary-color,#03a9f4);color:var(--text-primary-color,white)}.primary:hover{filter:brightness(.94);background:var(--primary-color,#03a9f4)}.danger{color:var(--error-color,#c62828);border-color:var(--divider-color,#ddd)}footer{position:sticky;bottom:0;background:var(--card-background-color,white);border-top:1px solid var(--divider-color,#ddd);padding:14px 24px;display:flex;align-items:center;justify-content:space-between;gap:12px;box-shadow:0 -2px 8px #0001}.footnote{font-size:13px;color:var(--secondary-text-color,#666)}.error{padding:12px;background:var(--error-state-color,#ffebee);color:var(--error-color,#b71c1c);border-radius:6px;margin:12px 0;overflow-wrap:anywhere}.saved{padding:10px 0;color:var(--success-color,#2e7d32)}dialog{color:var(--primary-text-color,#222);background:var(--card-background-color,white);border:1px solid var(--divider-color,#ddd);border-radius:16px;width:min(620px,95vw);max-height:88vh;padding:24px}dialog::backdrop{background:#0008}.form-fields{display:grid;gap:16px}.field{display:grid;gap:6px;font-size:14px}.field input:not([type=checkbox]),.field select,header select{width:100%;padding:11px;font:inherit;border-radius:6px;border:1px solid var(--divider-color,#aaa);color:var(--primary-text-color,#222);background:var(--card-background-color,white)}input:focus,select:focus,button:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:3px}.checks{display:grid;gap:9px}.check{display:flex;align-items:center;gap:10px}.dialog-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:24px}.resource{max-width:300px}a{color:var(--primary-color,#0288d1)}@media(max-width:760px){.grid{grid-template-columns:1fr}main{padding:20px 14px 80px}.card{padding:18px}footer{padding:12px 14px}h1{font-size:24px}}
`;

export class GridworksCommissioning extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:"open"}); this._busy=false; this._values={}; }
  set hass(value) { this._hass=value; if (this.isConnected && !this._started) this.start(); }
  get hass() { return this._hass; }
  connectedCallback() { if (this._hass && !this._started) this.start(); }
  disconnectedCallback() { const id=this._flowId; this._flowId=null; this._started=false; if (id) this._hass.callApi("DELETE", `${FLOW}/${id}`).catch(()=>{}); }
  async start() {
    this._started=true; this._busy=true; this.render();
    try {
      if (!this.hass.user?.is_admin) throw Error("An administrator account is required for commissioning.");
      this._entries=await this.hass.callApi("GET", `config/config_entries/entry?domain=${DOMAIN}`);
      const requested=new URLSearchParams(window.location.search).get("config_entry");
      this._entry=this._entries.find(item=>item.entry_id===requested) || (!requested ? this._entries[0] : null);
      if (!this._entry) throw Error("No matching GridWorks resource was found. Add the integration first, then open Configure.");
      await this.begin();
    } catch (err) { this._error=err.message || String(err); }
    finally { this._busy=false; this.render(); }
  }
  async begin() {
    const result=await this.hass.callApi("POST", FLOW, {handler:this._entry.entry_id});
    this._flowId=result.flow_id;
    this.apply(await this.hass.callApi("POST", `${FLOW}/${this._flowId}`, {next_step_id:"dashboard"}));
  }
  apply(result, keepValues=false) {
    if (result.type!=="form" || result.step_id!=="dashboard") throw Error("The commissioning response was incompatible. Refresh and check the installed connector version.");
    this._view=JSON.parse(result.description_placeholders.dashboard);
    if (!keepValues) this._values=this.defaults(this._view.form?.data_schema || []);
  }
  defaults(schema) {
    const values={};
    for (const field of schema) {
      const suggested=field.description?.suggested_value;
      if (suggested!==undefined) values[field.name]=suggested;
      else if (field.default!==undefined) values[field.name]=field.default;
      else if (field.selector?.boolean) values[field.name]=false;
    }
    return values;
  }
  async send(data) {
    if (this._busy) return;
    this._busy=true; this._error=null; this._saved=false; this.render();
    try {
      const result=await this.hass.callApi("POST", `${FLOW}/${this._flowId}`, data);
      if (result.type==="create_entry") {
        this._flowId=null; await this.begin(); this._saved=true;
      } else {
        const next=JSON.parse(result.description_placeholders.dashboard);
        this.apply(result, data.action==="submit" && !!(next.error || Object.keys(next.form?.errors || {}).length));
      }
    } catch (err) { this._error=err.message || "The edit session could not be updated. Refresh to reopen the saved configuration."; }
    finally { this._busy=false; this.render(); }
  }
  async discard(entry) {
    if (this._view?.dirty && !window.confirm("Discard the unsaved definition changes?")) { this.render(); return; }
    this._busy=true; this.render();
    try {
      if (this._flowId) await this.hass.callApi("DELETE", `${FLOW}/${this._flowId}`);
      this._flowId=null; if (entry) this._entry=entry;
      await this.begin(); this._saved=false; this._error=null;
    } catch(err) {this._error=err.message || String(err);}
    finally {this._busy=false;this.render();}
  }
  button(label, callback, options={}) { return node("button", {type:"button", text:label, disabled:this._busy, onClick:callback, ...options}); }
  render() {
    const main=node("main"); const header=node("header",{},[node("h1",{text:"Commission your resource"})]);
    if (this._entry) header.append(node("span",{text:this._entry.title,className:"resource"}));
    if (this._entries?.length>1) {
      const select=node("select",{"aria-label":"Resource",className:"resource",disabled:this._busy,onChange:e=>this.discard(this._entries.find(item=>item.entry_id===e.target.value))});
      for(const entry of this._entries) select.append(node("option",{value:entry.entry_id,text:entry.title,selected:entry.entry_id===this._entry?.entry_id}));
      header.append(select);
    }
    main.append(header,node("p",{className:"intro",text:"Review each category, see what is already selected, and add or edit the definitions you need. Your existing selections are preserved."}));
    if(this._error) main.append(node("div",{className:"error",role:"alert",text:this._error}));
    if(this._saved) main.append(node("div",{className:"saved",role:"status",text:"Configuration saved. The connector will reload with these definitions."}));
    if(this._view) {
      main.append(node("div",{className:"status",text:this._view.dirty ? "Unsaved changes — definitions below are a draft until you choose Save configuration." : "Showing your saved definitions. You can revisit any category at any time."}));
      if(this._view.error && !this._view.form) main.append(node("div",{className:"error",role:"alert",text:this._view.error}));
      const grid=node("div",{className:"grid"});
      for(const category of this._view.categories) {
        const card=node("section",{className:"card","aria-label":category.title},[node("h2",{text:category.title}),node("p",{className:"explanation",text:category.explanation})]);
        if(category.summary) card.append(node("p",{text:category.summary,className:"detail"}));
        for(const entry of category.entries) {
          const row=node("div",{className:"entry"},[node("div",{className:"entry-name",text:entry.label}),node("div",{className:"source",text:entry.source}),node("div",{className:"detail",text:entry.detail})]);
          row.append(node("div",{className:"actions"},[
            this.button("Edit",()=>this.send({action:"edit",target:entry.target}),{className:"small","aria-label":`Edit ${entry.label}`}),
            this.button("Remove",()=>{if(window.confirm(`Remove ${entry.label} from this draft?`))this.send({action:"remove",target:entry.target});},{className:"small danger","aria-label":`Remove ${entry.label}`})]));
          card.append(row);
        }
        if(!category.entries.length && category.id!=="cloud") card.append(node("div",{className:"empty",text:"No entries selected yet."}));
        const actions=node("div",{className:"actions"});
        for(const action of category.actions) actions.append(this.button(action.label,()=>this.send({action:"open",step:action.step,category:category.id})));
        card.append(actions);grid.append(card);
      }
      main.append(grid);
    } else if(this._busy) main.append(node("p",{text:"Opening your saved commissioning definitions…",role:"status"}));
    this.shadowRoot.replaceChildren(node("style",{text:style}),main);
    if(this._view) {
      const footer=node("footer",{},[node("span",{className:"footnote",text:"Shadow only · No equipment commands"}),node("div",{className:"actions"},[
        this.button("Discard changes",()=>this.discard(),{disabled:this._busy || !this._view.dirty}),
        this.button("Save configuration",()=>this.send({action:"save"}),{className:"primary",disabled:this._busy || !!this._view.form})])]);
      this.shadowRoot.append(footer);
      if(this._view.form) this.renderForm();
    }
  }
  renderForm() {
    const current=this._view.form; const step=current.step_id;
    const dialog=node("dialog",{"aria-label":titles[step]||human(step),onCancel:e=>{e.preventDefault();this.send({action:"back"});}});
    dialog.append(node("h2",{text:titles[step]||human(step)}));
    if(help[step]) dialog.append(node("p",{className:"explanation",text:help[step]}));
    if(this._view.error) dialog.append(node("div",{className:"error",role:"alert",text:this._view.error}));
    for(const code of Object.values(current.errors||{})) dialog.append(node("div",{className:"error",role:"alert",text:code==="weather_not_ready" ? "The shadow peer has not proposed weather sources yet. Save your definitions and return here after the peer connects." : code==="incomplete" ? "Add a temperature channel with valid limits before saving." : "Check the selected source, units, limits and referenced definitions."}));
    const form=node("form",{onSubmit:event=>{event.preventDefault();if(form.reportValidity())this.send({action:"submit",data:this.cleanValues(current.data_schema)});}});
    const fields=node("div",{className:"form-fields"});
    for(const field of current.data_schema) fields.append(this.renderField(field));
    form.append(fields,node("div",{className:"dialog-actions"},[
      this.button("Cancel",()=>this.send({action:"back"})),
      node("button",{type:"submit",className:"primary",text:step==="weather" ? "Confirm weather sources" : "Apply to draft",disabled:this._busy})]));
    dialog.append(form);this.shadowRoot.append(dialog);dialog.showModal();
  }
  cleanValues(schema) {
    const data={};
    for(const field of schema) {const value=this._values[field.name];if(value!==undefined && value!==null && value!=="")data[field.name]=value;}
    return data;
  }
  renderField(field) {
    const value=this._values[field.name];const selector=field.selector||{};const kind=Object.keys(selector)[0];const config=selector[kind]||{};
    const label=labels[field.name]||human(field.name);const box=node("div",{className:"field"});
    const id=`field-${field.name}`;const title=node("label",{htmlFor:id,text:label+(field.required?" *":"")});
    if(kind==="boolean" || field.type==="boolean") {
      box.append(node("label",{className:"check"},[node("input",{id,type:"checkbox",checked:!!value,disabled:this._busy,onChange:e=>this._values[field.name]=e.target.checked}),node("span",{text:label})]));return box;
    }
    box.append(title);
    const options=config.options||[];
    if(kind==="select" && config.multiple) {
      const checks=node("div",{className:"checks",role:"group","aria-label":label});
      for(const option of options) {const val=typeof option==="string"?option:option.value;const text=typeof option==="string"?human(option):option.label;checks.append(node("label",{className:"check"},[node("input",{type:"checkbox",checked:(value||[]).includes(val),onChange:e=>{const selected=new Set(this._values[field.name]||[]);if(e.target.checked)selected.add(val);else selected.delete(val);this._values[field.name]=[...selected];}}),node("span",{text})]));}
      box.append(checks);return box;
    }
    if(kind==="select") {
      const select=node("select",{id,name:field.name,required:!!field.required,disabled:this._busy,onChange:e=>this._values[field.name]=e.target.value});
      select.append(node("option",{value:"",text:"Select…"}));
      for(const option of options) {const val=typeof option==="string"?option:option.value;let text=typeof option==="string"?human(option):option.label;if(val==="local_demo")text="Embedded demonstration";if(val==="mqtt")text="Approved external MQTT peer";select.append(node("option",{value:val,text}));}
      select.value=value??"";box.append(select);return box;
    }
    const numeric=kind==="number" || field.type==="integer" || field.type==="float";
    const input=node("input",{id,name:field.name,type:numeric?"number":"text",value:value??"",required:!!field.required,disabled:this._busy,onInput:e=>this._values[field.name]=numeric&&e.target.value!==""?Number(e.target.value):e.target.value});
    if(numeric){input.step=config.step??"any";if(config.min!==undefined)input.min=config.min;if(config.max!==undefined)input.max=config.max;}
    if(kind==="entity") {
      const list=node("datalist",{id:`entities-${field.name}`});
      for(const [entityId,state] of Object.entries(this.hass.states||{}))list.append(node("option",{value:entityId,text:state.attributes?.friendly_name||entityId}));
      input.setAttribute("list",list.id);input.placeholder="Search or enter an existing entity ID";input.autocomplete="off";box.append(list);
    }
    box.append(input);return box;
  }
}
if(!customElements.get("gridworks-commissioning"))customElements.define("gridworks-commissioning",GridworksCommissioning);
