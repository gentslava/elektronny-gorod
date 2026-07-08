/* eg-intercom-call-card — собранный бандл. Источник: frontend/src/. Не редактировать вручную. */
var Xe=Object.defineProperty;var Ze=Object.getOwnPropertyDescriptor;var o=(s,t,e,i)=>{for(var r=i>1?void 0:i?Ze(t,e):t,n=s.length-1,a;n>=0;n--)(a=s[n])&&(r=(i?a(t,e,r):a(r))||r);return i&&r&&Xe(t,e,r),r};var X=globalThis,Z=X.ShadowRoot&&(X.ShadyCSS===void 0||X.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,ae=Symbol(),be=new WeakMap,D=class{constructor(t,e,i){if(this._$cssResult$=!0,i!==ae)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(Z&&t===void 0){let i=e!==void 0&&e.length===1;i&&(t=be.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&be.set(e,t))}return t}toString(){return this.cssText}},xe=s=>new D(typeof s=="string"?s:s+"",void 0,ae),x=(s,...t)=>{let e=s.length===1?s[0]:t.reduce((i,r,n)=>i+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+s[n+1],s[0]);return new D(e,s,ae)},ye=(s,t)=>{if(Z)s.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let i=document.createElement("style"),r=X.litNonce;r!==void 0&&i.setAttribute("nonce",r),i.textContent=e.cssText,s.appendChild(i)}},oe=Z?s=>s:s=>s instanceof CSSStyleSheet?(t=>{let e="";for(let i of t.cssRules)e+=i.cssText;return xe(e)})(s):s;var{is:Je,defineProperty:Qe,getOwnPropertyDescriptor:et,getOwnPropertyNames:tt,getOwnPropertySymbols:it,getPrototypeOf:rt}=Object,J=globalThis,we=J.trustedTypes,st=we?we.emptyScript:"",nt=J.reactiveElementPolyfillSupport,B=(s,t)=>s,j={toAttribute(s,t){switch(t){case Boolean:s=s?st:null;break;case Object:case Array:s=s==null?s:JSON.stringify(s)}return s},fromAttribute(s,t){let e=s;switch(t){case Boolean:e=s!==null;break;case Number:e=s===null?null:Number(s);break;case Object:case Array:try{e=JSON.parse(s)}catch{e=null}}return e}},Q=(s,t)=>!Je(s,t),$e={attribute:!0,type:String,converter:j,reflect:!1,useDefault:!1,hasChanged:Q};Symbol.metadata??=Symbol("metadata"),J.litPropertyMetadata??=new WeakMap;var M=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=$e){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let i=Symbol(),r=this.getPropertyDescriptor(t,i,e);r!==void 0&&Qe(this.prototype,t,r)}}static getPropertyDescriptor(t,e,i){let{get:r,set:n}=et(this.prototype,t)??{get(){return this[e]},set(a){this[e]=a}};return{get:r,set(a){let p=r?.call(this);n?.call(this,a),this.requestUpdate(t,p,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??$e}static _$Ei(){if(this.hasOwnProperty(B("elementProperties")))return;let t=rt(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(B("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(B("properties"))){let e=this.properties,i=[...tt(e),...it(e)];for(let r of i)this.createProperty(r,e[r])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[i,r]of e)this.elementProperties.set(i,r)}this._$Eh=new Map;for(let[e,i]of this.elementProperties){let r=this._$Eu(e,i);r!==void 0&&this._$Eh.set(r,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let i=new Set(t.flat(1/0).reverse());for(let r of i)e.unshift(oe(r))}else t!==void 0&&e.push(oe(t));return e}static _$Eu(t,e){let i=e.attribute;return i===!1?void 0:typeof i=="string"?i:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ye(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){let i=this.constructor.elementProperties.get(t),r=this.constructor._$Eu(t,i);if(r!==void 0&&i.reflect===!0){let n=(i.converter?.toAttribute!==void 0?i.converter:j).toAttribute(e,i.type);this._$Em=t,n==null?this.removeAttribute(r):this.setAttribute(r,n),this._$Em=null}}_$AK(t,e){let i=this.constructor,r=i._$Eh.get(t);if(r!==void 0&&this._$Em!==r){let n=i.getPropertyOptions(r),a=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:j;this._$Em=r;let p=a.fromAttribute(e,n.type);this[r]=p??this._$Ej?.get(r)??p,this._$Em=null}}requestUpdate(t,e,i,r=!1,n){if(t!==void 0){let a=this.constructor;if(r===!1&&(n=this[t]),i??=a.getPropertyOptions(t),!((i.hasChanged??Q)(n,e)||i.useDefault&&i.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(a._$Eu(t,i))))return;this.C(t,e,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:r,wrapped:n},a){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,a??e??this[t]),n!==!0||a!==void 0)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),r===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[r,n]of this._$Ep)this[r]=n;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[r,n]of i){let{wrapped:a}=n,p=this[r];a!==!0||this._$AL.has(r)||p===void 0||this.C(r,void 0,n,p)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(e)):this._$EM()}catch(i){throw t=!1,this._$EM(),i}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};M.elementStyles=[],M.shadowRootOptions={mode:"open"},M[B("elementProperties")]=new Map,M[B("finalized")]=new Map,nt?.({ReactiveElement:M}),(J.reactiveElementVersions??=[]).push("2.1.2");var ge=globalThis,Ae=s=>s,ee=ge.trustedTypes,ke=ee?ee.createPolicy("lit-html",{createHTML:s=>s}):void 0,Ee="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,Re="?"+P,at=`<${Re}>`,R=document,V=()=>R.createComment(""),I=s=>s===null||typeof s!="object"&&typeof s!="function",me=Array.isArray,ot=s=>me(s)||typeof s?.[Symbol.iterator]=="function",ce=`[ 	
\f\r]`,q=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Se=/-->/g,Me=/>/g,C=RegExp(`>|${ce}(?:([^\\s"'>=/]+)(${ce}*=${ce}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Te=/'/g,Pe=/"/g,Oe=/^(?:script|style|textarea|title)$/i,fe=s=>(t,...e)=>({_$litType$:s,strings:t,values:e}),c=fe(1),Rt=fe(2),Ot=fe(3),T=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),Ce=new WeakMap,E=R.createTreeWalker(R,129);function He(s,t){if(!me(s)||!s.hasOwnProperty("raw"))throw Error("invalid template strings array");return ke!==void 0?ke.createHTML(t):t}var ct=(s,t)=>{let e=s.length-1,i=[],r,n=t===2?"<svg>":t===3?"<math>":"",a=q;for(let p=0;p<e;p++){let d=s[p],g,f,h=-1,w=0;for(;w<d.length&&(a.lastIndex=w,f=a.exec(d),f!==null);)w=a.lastIndex,a===q?f[1]==="!--"?a=Se:f[1]!==void 0?a=Me:f[2]!==void 0?(Oe.test(f[2])&&(r=RegExp("</"+f[2],"g")),a=C):f[3]!==void 0&&(a=C):a===C?f[0]===">"?(a=r??q,h=-1):f[1]===void 0?h=-2:(h=a.lastIndex-f[2].length,g=f[1],a=f[3]===void 0?C:f[3]==='"'?Pe:Te):a===Pe||a===Te?a=C:a===Se||a===Me?a=q:(a=C,r=void 0);let $=a===C&&s[p+1].startsWith("/>")?" ":"";n+=a===q?d+at:h>=0?(i.push(g),d.slice(0,h)+Ee+d.slice(h)+P+$):d+P+(h===-2?p:$)}return[He(s,n+(s[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),i]},W=class s{constructor({strings:t,_$litType$:e},i){let r;this.parts=[];let n=0,a=0,p=t.length-1,d=this.parts,[g,f]=ct(t,e);if(this.el=s.createElement(g,i),E.currentNode=this.el.content,e===2||e===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(r=E.nextNode())!==null&&d.length<p;){if(r.nodeType===1){if(r.hasAttributes())for(let h of r.getAttributeNames())if(h.endsWith(Ee)){let w=f[a++],$=r.getAttribute(h).split(P),Y=/([.?@])?(.*)/.exec(w);d.push({type:1,index:n,name:Y[2],strings:$,ctor:Y[1]==="."?de:Y[1]==="?"?pe:Y[1]==="@"?he:L}),r.removeAttribute(h)}else h.startsWith(P)&&(d.push({type:6,index:n}),r.removeAttribute(h));if(Oe.test(r.tagName)){let h=r.textContent.split(P),w=h.length-1;if(w>0){r.textContent=ee?ee.emptyScript:"";for(let $=0;$<w;$++)r.append(h[$],V()),E.nextNode(),d.push({type:2,index:++n});r.append(h[w],V())}}}else if(r.nodeType===8)if(r.data===Re)d.push({type:2,index:n});else{let h=-1;for(;(h=r.data.indexOf(P,h+1))!==-1;)d.push({type:7,index:n}),h+=P.length-1}n++}}static createElement(t,e){let i=R.createElement("template");return i.innerHTML=t,i}};function H(s,t,e=s,i){if(t===T)return t;let r=i!==void 0?e._$Co?.[i]:e._$Cl,n=I(t)?void 0:t._$litDirective$;return r?.constructor!==n&&(r?._$AO?.(!1),n===void 0?r=void 0:(r=new n(s),r._$AT(s,e,i)),i!==void 0?(e._$Co??=[])[i]=r:e._$Cl=r),r!==void 0&&(t=H(s,r._$AS(s,t.values),r,i)),t}var le=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:i}=this._$AD,r=(t?.creationScope??R).importNode(e,!0);E.currentNode=r;let n=E.nextNode(),a=0,p=0,d=i[0];for(;d!==void 0;){if(a===d.index){let g;d.type===2?g=new K(n,n.nextSibling,this,t):d.type===1?g=new d.ctor(n,d.name,d.strings,this,t):d.type===6&&(g=new ue(n,this,t)),this._$AV.push(g),d=i[++p]}a!==d?.index&&(n=E.nextNode(),a++)}return E.currentNode=R,r}p(t){let e=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}},K=class s{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,r){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=H(this,t,e),I(t)?t===l||t==null||t===""?(this._$AH!==l&&this._$AR(),this._$AH=l):t!==this._$AH&&t!==T&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):ot(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==l&&I(this._$AH)?this._$AA.nextSibling.data=t:this.T(R.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:i}=t,r=typeof i=="number"?this._$AC(t):(i.el===void 0&&(i.el=W.createElement(He(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(e);else{let n=new le(r,this),a=n.u(this.options);n.p(e),this.T(a),this._$AH=n}}_$AC(t){let e=Ce.get(t.strings);return e===void 0&&Ce.set(t.strings,e=new W(t)),e}k(t){me(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,i,r=0;for(let n of t)r===e.length?e.push(i=new s(this.O(V()),this.O(V()),this,this.options)):i=e[r],i._$AI(n),r++;r<e.length&&(this._$AR(i&&i._$AB.nextSibling,r),e.length=r)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let i=Ae(t).nextSibling;Ae(t).remove(),t=i}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},L=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,r,n){this.type=1,this._$AH=l,this._$AN=void 0,this.element=t,this.name=e,this._$AM=r,this.options=n,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=l}_$AI(t,e=this,i,r){let n=this.strings,a=!1;if(n===void 0)t=H(this,t,e,0),a=!I(t)||t!==this._$AH&&t!==T,a&&(this._$AH=t);else{let p=t,d,g;for(t=n[0],d=0;d<n.length-1;d++)g=H(this,p[i+d],e,d),g===T&&(g=this._$AH[d]),a||=!I(g)||g!==this._$AH[d],g===l?t=l:t!==l&&(t+=(g??"")+n[d+1]),this._$AH[d]=g}a&&!r&&this.j(t)}j(t){t===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},de=class extends L{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===l?void 0:t}},pe=class extends L{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==l)}},he=class extends L{constructor(t,e,i,r,n){super(t,e,i,r,n),this.type=5}_$AI(t,e=this){if((t=H(this,t,e,0)??l)===T)return;let i=this._$AH,r=t===l&&i!==l||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,n=t!==l&&(i===l||r);r&&this.element.removeEventListener(this.name,this,i),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},ue=class{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){H(this,t)}};var lt=ge.litHtmlPolyfillSupport;lt?.(W,K),(ge.litHtmlVersions??=[]).push("3.3.3");var Le=(s,t,e)=>{let i=e?.renderBefore??t,r=i._$litPart$;if(r===void 0){let n=e?.renderBefore??null;i._$litPart$=r=new K(t.insertBefore(V(),n),n,void 0,e??{})}return r._$AI(s),r};var ve=globalThis,b=class extends M{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=Le(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return T}};b._$litElement$=!0,b.finalized=!0,ve.litElementHydrateSupport?.({LitElement:b});var dt=ve.litElementPolyfillSupport;dt?.({LitElement:b});(ve.litElementVersions??=[]).push("4.2.2");var k=s=>(t,e)=>{e!==void 0?e.addInitializer(()=>{customElements.define(s,t)}):customElements.define(s,t)};var pt={attribute:!0,type:String,converter:j,reflect:!1,hasChanged:Q},ht=(s=pt,t,e)=>{let{kind:i,metadata:r}=e,n=globalThis.litPropertyMetadata.get(r);if(n===void 0&&globalThis.litPropertyMetadata.set(r,n=new Map),i==="setter"&&((s=Object.create(s)).wrapped=!0),n.set(e.name,s),i==="accessor"){let{name:a}=e;return{set(p){let d=t.get.call(this);t.set.call(this,p),this.requestUpdate(a,d,s,!0,p)},init(p){return p!==void 0&&this.C(a,void 0,s,p),p}}}if(i==="setter"){let{name:a}=e;return function(p){let d=this[a];t.call(this,p),this.requestUpdate(a,d,s,!0,p)}}throw Error("Unsupported decorator location: "+i)};function u(s){return(t,e)=>typeof e=="object"?ht(s,t,e):((i,r,n)=>{let a=r.hasOwnProperty(n);return r.constructor.createProperty(n,i),a?Object.getOwnPropertyDescriptor(r,n):void 0})(s,t,e)}function v(s){return u({...s,state:!0,attribute:!1})}var ut=new Set(["idle","ringing","connecting","active","ended","error"]);function Ue(s){return s&&ut.has(s)?s:"idle"}var U={visible:!1,video:"none",actions:[],showOpen:!1,showTimer:!1,showAnswerWindow:!1,busy:!1,isError:!1};function Ne(s){switch(s){case"ringing":return{...U,visible:!0,video:"doorbell",actions:["reject","accept"],showOpen:!0,showAnswerWindow:!0};case"connecting":return{...U,visible:!0,video:"doorbell",actions:["cancel","connecting"],showOpen:!0,busy:!0};case"active":return{...U,visible:!0,video:"call",actions:["mic","sound","hangup"],showOpen:!0,showTimer:!0};case"error":return{...U,visible:!0,video:"none",actions:["retry","hangup"],showOpen:!0,isError:!0};case"ended":return{...U,visible:!0,video:"call",actions:["close"],showOpen:!0};case"idle":default:return{...U}}}function ze(s){return(s?.locale?.language??s?.language??"").toLowerCase().startsWith("en")?"en":"ru"}var De={status:{ringing:"\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432",connecting:"\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435\u2026",active:"\u0420\u0430\u0437\u0433\u043E\u0432\u043E\u0440",ended:"\u0412\u044B\u0437\u043E\u0432 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043D",error:"\u041E\u0448\u0438\u0431\u043A\u0430 \u0432\u044B\u0437\u043E\u0432\u0430"},compact:{call:"\u0412\u044B\u0437\u043E\u0432",talk:"\u0420\u0430\u0437\u0433\u043E\u0432\u043E\u0440",connecting:"\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435\u2026",ended:"\u0417\u0430\u0432\u0435\u0440\u0448\u0451\u043D",error:"\u041E\u0448\u0438\u0431\u043A\u0430 \u0432\u044B\u0437\u043E\u0432\u0430"},nameFallback:"\u0414\u043E\u043C\u043E\u0444\u043E\u043D",minimize:"\u0421\u0432\u0435\u0440\u043D\u0443\u0442\u044C",idle:{title:"\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u044B\u0437\u043E\u0432\u0430",sub:"\u0412\u0438\u0434\u0435\u043E \u043F\u043E\u044F\u0432\u0438\u0442\u0441\u044F \u043F\u0440\u0438 \u0437\u0432\u043E\u043D\u043A\u0435 \u0432 \u0434\u043E\u043C\u043E\u0444\u043E\u043D"},action:{accept:"\u041F\u0440\u0438\u043D\u044F\u0442\u044C",reject:"\u041E\u0442\u043A\u043B\u043E\u043D\u0438\u0442\u044C",cancel:"\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C",connecting:"\u0421\u043E\u0435\u0434\u0438\u043D\u044F\u0435\u043C\u2026",hangup:"\u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C",retry:"\u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C",close:"\u0417\u0430\u043A\u0440\u044B\u0442\u044C",sound:"\u0417\u0432\u0443\u043A",soundOff:"\u0417\u0432\u0443\u043A \u0432\u044B\u043A\u043B.",mic:"\u041C\u0438\u043A\u0440\u043E\u0444\u043E\u043D",micNoAccess:"\u041D\u0435\u0442 \u0434\u043E\u0441\u0442\u0443\u043F\u0430",micOn:"\u0412\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D",micOff:"\u0412\u044B\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D"},micBanner:{no_https:{title:"\u041C\u0438\u043A\u0440\u043E\u0444\u043E\u043D \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D",sub:"\u041E\u0442\u043A\u0440\u043E\u0439\u0442\u0435 Home Assistant \u043F\u043E HTTPS, \u0447\u0442\u043E\u0431\u044B \u0433\u043E\u0432\u043E\u0440\u0438\u0442\u044C \u0432 \u0434\u043E\u043C\u043E\u0444\u043E\u043D."},denied:{title:"\u0414\u043E\u0441\u0442\u0443\u043F \u043A \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D\u0443 \u0437\u0430\u043F\u0440\u0435\u0449\u0451\u043D",sub:"\u0420\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u0435 \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D \u0434\u043B\u044F \u044D\u0442\u043E\u0433\u043E \u0441\u0430\u0439\u0442\u0430 \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0430\u0445 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0430.",cta:"\u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C"},prompt:{title:"\u041D\u0443\u0436\u0435\u043D \u0434\u043E\u0441\u0442\u0443\u043F \u043A \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D\u0443",sub:"\u041D\u0430\u0436\u043C\u0438\u0442\u0435 \xAB\u0420\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u044C\xBB, \u0447\u0442\u043E\u0431\u044B \u0432\u0430\u0441 \u0431\u044B\u043B\u043E \u0441\u043B\u044B\u0448\u043D\u043E.",cta:"\u0420\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u044C"}},stage:{cameraOff:{title:"\u0412\u0438\u0434\u0435\u043E \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u043E",sub:"\u0410\u0443\u0434\u0438\u043E\u0432\u044B\u0437\u043E\u0432 \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0430\u0435\u0442\u0441\u044F"},connectionLost:{title:"\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435 \u043F\u0440\u0435\u0440\u0432\u0430\u043D\u043E",sub:"\u041F\u0440\u043E\u0431\u0443\u0435\u043C \u0432\u043E\u0441\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C\u2026"},soundOffChip:"\u0417\u0432\u0443\u043A \u0432\u044B\u043A\u043B.",unmuteAria:"\u0412\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u0437\u0432\u0443\u043A",unmuteCta:"\u041D\u0430\u0436\u043C\u0438\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u0432\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u0437\u0432\u0443\u043A"},video:{noVideo:"\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u0438\u0434\u0435\u043E",cameraUnavailable:"\u041A\u0430\u043C\u0435\u0440\u0430 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u0430",loading:"\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0432\u0438\u0434\u0435\u043E\u2026",playerUnavailable:"\u0412\u0438\u0434\u0435\u043E\u043F\u043B\u0435\u0435\u0440 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D \u2014 \u043E\u0431\u043D\u043E\u0432\u0438\u0442\u0435 HA \u0438\u043B\u0438 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u0435 advanced-camera-card"},open:{labelDefault:"\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C",opened:"\u041E\u0442\u043A\u0440\u044B\u0442\u043E",opening:"\u041E\u0442\u043A\u0440\u044B\u0432\u0430\u044E\u2026",slide:"\u041E\u0442\u043A\u0440\u044B\u0442\u044C",hold:"\u0423\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0439\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u043E\u0442\u043A\u0440\u044B\u0442\u044C",captionOpened:"\u0414\u0432\u0435\u0440\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u0430",captionError:"\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u044C \xB7 \u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C",captionSlideHint:"\u0421\u0434\u0432\u0438\u043D\u044C\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C",holdAriaSuffix:"\u2014 \u0443\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0439\u0442\u0435"}},gt={status:{ringing:"Incoming call",connecting:"Connecting\u2026",active:"In call",ended:"Call ended",error:"Call error"},compact:{call:"Call",talk:"In call",connecting:"Connecting\u2026",ended:"Ended",error:"Call error"},nameFallback:"Intercom",minimize:"Minimize",idle:{title:"No active call",sub:"Video appears when someone calls"},action:{accept:"Answer",reject:"Decline",cancel:"Cancel",connecting:"Connecting\u2026",hangup:"Hang up",retry:"Retry",close:"Close",sound:"Sound",soundOff:"Sound off",mic:"Mic",micNoAccess:"No access",micOn:"Turn microphone on",micOff:"Turn microphone off"},micBanner:{no_https:{title:"Microphone unavailable",sub:"Open Home Assistant over HTTPS to talk to the intercom."},denied:{title:"Microphone blocked",sub:"Allow the microphone for this site in your browser settings.",cta:"Retry"},prompt:{title:"Microphone access needed",sub:"Tap \u201CAllow\u201D so you can be heard.",cta:"Allow"}},stage:{cameraOff:{title:"Video unavailable",sub:"Audio call continues"},connectionLost:{title:"Connection lost",sub:"Trying to reconnect\u2026"},soundOffChip:"Sound off",unmuteAria:"Turn sound on",unmuteCta:"Tap to turn on sound"},video:{noVideo:"No active video",cameraUnavailable:"Camera unavailable",loading:"Loading video\u2026",playerUnavailable:"Video player unavailable \u2014 update HA or install advanced-camera-card"},open:{labelDefault:"Open door",opened:"Opened",opening:"Opening\u2026",slide:"Open",hold:"Hold to open",captionOpened:"Door opened",captionError:"Couldn\u2019t open \xB7 Retry",captionSlideHint:"Slide to open the door",holdAriaSuffix:"\u2014 hold"}},mt={ru:De,en:gt};function m(s){return mt[s]??De}var Be={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},re=s=>(...t)=>({_$litDirective$:s,values:t}),ie=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,i){this._$Ct=t,this._$AM=e,this._$Ci=i}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var O=class extends ie{constructor(t){if(super(t),this.it=l,t.type!==Be.CHILD)throw Error(this.constructor.directiveName+"() can only be used in child bindings")}render(t){if(t===l||t==null)return this._t=void 0,this.it=t;if(t===T)return t;if(typeof t!="string")throw Error(this.constructor.directiveName+"() called with a non-string value");if(t===this.it)return this._t;this.it=t;let e=[t];return e.raw=e,this._t={_$litType$:this.constructor.resultType,strings:e,values:[]}}};O.directiveName="unsafeHTML",O.resultType=1;var Ai=re(O);var G=class extends O{};G.directiveName="unsafeSVG",G.resultType=2;var je=re(G);var ft={"key-round":'<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',lock:'<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',"lock-open":'<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',phone:'<path d="M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"/>',"phone-off":'<path d="M10.1 13.9a14 14 0 0 0 3.732 2.668 1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2 18 18 0 0 1-12.728-5.272"/><path d="M22 2 2 22"/><path d="M4.76 13.582A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 .244.473"/>',mic:'<path d="M12 19v3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><rect x="9" y="2" width="6" height="13" rx="3"/>',"mic-off":'<path d="M12 19v3"/><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33"/><path d="M16.95 16.95A7 7 0 0 1 5 12v-2"/><path d="M18.89 13.23A7 7 0 0 0 19 12v-2"/><path d="m2 2 20 20"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12"/>',"volume-2":'<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',"volume-x":'<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><line x1="22" x2="16" y1="9" y2="15"/><line x1="16" x2="22" y1="9" y2="15"/>',x:'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',timer:'<line x1="10" x2="14" y1="2" y2="2"/><line x1="12" x2="15" y1="14" y2="11"/><circle cx="12" cy="14" r="8"/>',"refresh-cw":'<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',"door-open":'<path d="M11 20H2"/><path d="M11 4.562v16.157a1 1 0 0 0 1.242.97L19 20V5.562a2 2 0 0 0-1.515-1.94l-4-1A2 2 0 0 0 11 4.561z"/><path d="M11 4H8a2 2 0 0 0-2 2v14"/><path d="M14 12h.01"/><path d="M22 20h-3"/>',"video-off":'<path d="M10.66 6H14a2 2 0 0 1 2 2v2.5l5.248-3.062A.5.5 0 0 1 22 7.87v8.196"/><path d="M16 16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h2"/><path d="m2 2 20 20"/>',"wifi-off":'<path d="M12 20h.01"/><path d="M8.5 16.429a5 5 0 0 1 7 0"/><path d="M5 12.859a10 10 0 0 1 5.17-2.69"/><path d="M19 12.859a10 10 0 0 0-2.007-1.523"/><path d="M2 8.82a15 15 0 0 1 4.177-2.643"/><path d="M22 8.82a15 15 0 0 0-11.288-3.764"/><path d="m2 2 20 20"/>',"circle-check":'<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',"chevron-right":'<path d="m9 18 6-6-6-6"/>',"bell-ring":'<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M22 8c0-2.3-.8-4.3-2-6"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/><path d="M4 2C2.8 3.7 2 5.7 2 8"/>',"loader-circle":'<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',"door-closed":'<path d="M10 12h.01"/><path d="M18 20V6a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v14"/><path d="M2 20h20"/>'},N=class extends b{constructor(){super(...arguments);this.name=""}render(){let e=ft[this.name]??"";return c`<svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >${je(e)}</svg>`}};N.styles=x`
    :host {
      display: inline-flex;
      width: var(--eg-icon-size, 24px);
      height: var(--eg-icon-size, 24px);
      line-height: 0;
      flex: none;
    }
    svg {
      width: 100%;
      height: 100%;
      display: block;
    }
  `,o([u()],N.prototype,"name",2),N=o([k("eg-icon")],N);function qe(s,t){if(s==="call")return t.camera;if(s==="doorbell")return t.doorbell_camera??t.camera}var S=class extends b{constructor(){super(...arguments);this.muted=!1;this.uiLang="ru";this._provider="pending"}connectedCallback(){super.connectedCallback(),this._resolveProvider()}async _resolveProvider(){if(customElements.get("ha-camera-stream")){this._provider="ha";return}try{await window.loadCardHelpers?.()}catch{}customElements.get("ha-camera-stream")?this._provider="ha":customElements.get("webrtc-camera")?this._provider="webrtc":this._provider="none"}updated(e){this._provider==="webrtc"&&this._syncWebrtc(e)}_syncWebrtc(e){let i=this.renderRoot.querySelector("#webrtc-host");if(!(!i||!this.entity||!this.hass))if(e.has("entity")||e.has("_provider")||e.has("muted")||!this._webrtcEl){i.replaceChildren();let r=document.createElement("webrtc-camera");r.setConfig({entity:this.entity,muted:this.muted}),r.hass=this.hass,i.appendChild(r),this._webrtcEl=r}else this._webrtcEl.hass=this.hass}render(){let e=m(this.uiLang).video;if(!this.entity||!this.hass)return this._frame("video-off",e.noVideo);let i=this.hass.states[this.entity];if(!i)return this._frame("video-off",e.cameraUnavailable);switch(this._provider){case"pending":return this._frame("video-off",e.loading);case"ha":return c`
          <ha-camera-stream
            .hass=${this.hass}
            .stateObj=${i}
            .muted=${this.muted}
          ></ha-camera-stream>
        `;case"webrtc":return c`<div id="webrtc-host"></div>`;default:return this._frame("video-off",e.playerUnavailable)}}_frame(e,i){return c`
      <div class="frame" role="img" aria-label=${i}>
        <eg-icon name=${e}></eg-icon>
        <span>${i}</span>
      </div>
      ${l}
    `}};S.styles=x`
    :host {
      display: block;
      width: 100%;
      height: 100%;
    }
    ha-camera-stream,
    #webrtc-host {
      display: block;
      width: 100%;
      height: 100%;
    }
    /* реальный плеер заполняет область (object-fit самого видео — по потоку) */
    .frame {
      width: 100%;
      height: 100%;
      background: var(--secondary-background-color);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      color: var(--secondary-text-color);
      text-align: center;
      padding: 8px;
      box-sizing: border-box;
    }
    .frame eg-icon {
      --eg-icon-size: 40px;
    }
    .frame span {
      font-size: 0.85rem;
    }
  `,o([u({attribute:!1})],S.prototype,"hass",2),o([u()],S.prototype,"entity",2),o([u({type:Boolean})],S.prototype,"muted",2),o([u()],S.prototype,"uiLang",2),o([v()],S.prototype,"_provider",2),S=o([k("eg-call-video")],S);var z=x`
  :host {
    --eg-primary: var(--primary-color, #03a9f4);
    --eg-success: var(--success-color, #4caf50);
    --eg-error: var(--error-color, #ef5350);
    --eg-warning: var(--warning-color, #ffb300);
    --eg-text: var(--primary-text-color, #e8e8e8);
    --eg-text-2: var(--secondary-text-color, #a6a6a6);
    --eg-text-3: var(--disabled-text-color, #787878);
    --eg-elevated: var(--secondary-background-color, #2a2a2a);
    --eg-card: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --eg-divider: var(--divider-color, #2e2e2e);
    --eg-on-fill: var(--text-primary-color, #ffffff);
    --eg-scrim: rgba(0, 0, 0, 0.72);
    --eg-r-card: 16px;
    --eg-r-md: 12px;
    --eg-r-full: 999px;
    --eg-mono: "Roboto Mono", ui-monospace, monospace;
    /* Тинты бейджей/баннеров = роль-цвет @ ~18% (эквивалент alpha 2E/1A из макета). */
    --eg-primary-bg: color-mix(in srgb, var(--eg-primary) 18%, transparent);
    --eg-success-bg: color-mix(in srgb, var(--eg-success) 18%, transparent);
    --eg-error-bg: color-mix(in srgb, var(--eg-error) 18%, transparent);
    --eg-warning-bg: color-mix(in srgb, var(--eg-warning) 18%, transparent);
  }
`,vt={idle:"var(--eg-text-2)",ringing:"var(--eg-warning)",connecting:"var(--eg-primary)",active:"var(--eg-success)",ended:"var(--eg-text-2)",error:"var(--eg-error)"};function _e(s){return vt[s]??"var(--eg-text-2)"}function _t(s){switch(s){case"camera_off":return"placeholder-camera";case"connection_lost":return"placeholder-connection";case"ended":return"video-dimmed";default:return"video"}}var y=class extends b{constructor(){super(...arguments);this.muted=!1;this.live=!1;this.soundOff=!1;this.stageState="live";this.audioBlocked=!1;this.uiLang="ru";this._unmute=()=>{this.dispatchEvent(new CustomEvent("unmute",{bubbles:!0,composed:!0}))}}render(){let e=m(this.uiLang),i=_t(this.stageState);return i==="placeholder-camera"?this._placeholder("video-off","muted",e.stage.cameraOff.title,e.stage.cameraOff.sub):i==="placeholder-connection"?this._placeholder("wifi-off","err",e.stage.connectionLost.title,e.stage.connectionLost.sub):c`
      <eg-call-video .hass=${this.hass} .uiLang=${this.uiLang} .entity=${this.entity} .muted=${this.muted}></eg-call-video>
      ${i==="video-dimmed"?c`<div class="dim" aria-hidden="true"></div>`:l}
      <div class="top">
        ${this.live?c`<span class="live"><span class="live-dot" aria-hidden="true"></span>LIVE</span>`:l}
        ${this.soundOff?c`<span class="chip"><eg-icon name="volume-x"></eg-icon>${e.stage.soundOffChip}</span>`:l}
      </div>
      ${this.audioBlocked?c`
            <button class="tap" @click=${this._unmute} aria-label=${e.stage.unmuteAria}></button>
            <span class="cta" aria-hidden="true">
              <eg-icon name="volume-x"></eg-icon>${e.stage.unmuteCta}
            </span>
          `:l}
    `}_placeholder(e,i,r,n){return c`
      <div class="fallback ${i}" role="img" aria-label=${r}>
        <eg-icon name=${e}></eg-icon>
        <span class="fb-title">${r}</span>
        <span class="fb-sub">${n}</span>
      </div>
    `}};y.styles=[z,x`
      :host {
        position: absolute;
        inset: 0;
        display: block;
      }
      eg-call-video {
        position: absolute;
        inset: 0;
      }
      .dim {
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.5);
      }
      /* верхний ряд оверлеев: LIVE (слева) + чип звука (справа) */
      .top {
        position: absolute;
        top: calc(12px * var(--eg-scale, 1));
        left: calc(12px * var(--eg-scale, 1));
        right: calc(12px * var(--eg-scale, 1));
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        pointer-events: none;
      }
      .live {
        display: inline-flex;
        align-items: center;
        gap: calc(6px * var(--eg-scale, 1));
        padding: calc(3px * var(--eg-scale, 1)) calc(9px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: rgba(211, 47, 47, 0.88);
        color: #fff;
        font-size: calc(10px * var(--eg-scale, 1));
        font-weight: 600;
        letter-spacing: 0.04em;
      }
      .live-dot {
        width: calc(6px * var(--eg-scale, 1));
        height: calc(6px * var(--eg-scale, 1));
        border-radius: 50%;
        background: #fff;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: calc(6px * var(--eg-scale, 1));
        padding: calc(5px * var(--eg-scale, 1)) calc(10px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: rgba(0, 0, 0, 0.63);
        color: #fff;
        font-size: calc(11px * var(--eg-scale, 1));
      }
      .chip eg-icon {
        --eg-icon-size: calc(14px * var(--eg-scale, 1));
      }
      /* CTA «включить звук» + прозрачный tap-слой поверх всего видео */
      .tap {
        position: absolute;
        inset: 0;
        border: none;
        background: transparent;
        cursor: pointer;
        z-index: 2;
      }
      /* CTA — в НИЖНЕЙ части видео (не перекрывает лицо звонящего), UX §8/§13 */
      .cta {
        position: absolute;
        left: 50%;
        bottom: calc(16px * var(--eg-scale, 1));
        transform: translateX(-50%);
        display: inline-flex;
        align-items: center;
        gap: calc(8px * var(--eg-scale, 1));
        padding: calc(10px * var(--eg-scale, 1)) calc(18px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: var(--eg-scrim);
        color: #fff;
        font-size: calc(13px * var(--eg-scale, 1));
        font-weight: 500;
        white-space: nowrap;
        z-index: 3;
        pointer-events: none;
      }
      .cta eg-icon {
        --eg-icon-size: calc(18px * var(--eg-scale, 1));
      }
      /* плейсхолдеры (камера недоступна / связь прервана) */
      .fallback {
        position: absolute;
        inset: 0;
        background: var(--eg-card);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: calc(6px * var(--eg-scale, 1));
        text-align: center;
        padding: calc(12px * var(--eg-scale, 1));
        box-sizing: border-box;
      }
      .fallback eg-icon {
        --eg-icon-size: calc(36px * var(--eg-scale, 1));
        color: var(--eg-text-3);
      }
      .fallback.err eg-icon {
        color: var(--eg-error);
      }
      .fb-title {
        font-size: calc(15px * var(--eg-scale, 1));
        color: var(--eg-text);
      }
      .fb-sub {
        font-size: calc(12px * var(--eg-scale, 1));
        color: var(--eg-text-2);
      }
    `],o([u({attribute:!1})],y.prototype,"hass",2),o([u()],y.prototype,"entity",2),o([u({type:Boolean})],y.prototype,"muted",2),o([u({type:Boolean})],y.prototype,"live",2),o([u({type:Boolean})],y.prototype,"soundOff",2),o([u()],y.prototype,"stageState",2),o([u({type:Boolean})],y.prototype,"audioBlocked",2),o([u()],y.prototype,"uiLang",2),y=o([k("eg-call-stage")],y);function Ie(s){return s<0?0:s>1?1:s}function bt(s,t,e,i){let r=Math.max(1,e-i);return Ie((s-t-i/2)/r)}function xt(s,t){return Ie(s/Math.max(1,t))}var yt=.92,wt=800,Ve=68,A=class extends b{constructor(){super(...arguments);this.mode="hold";this.disabled=!1;this.label="";this.uiLang="ru";this.status="idle";this._progress=0;this._arming=!1;this._raf=0;this._holdStart=0;this._trackRect=null;this._knobW=Ve;this._holdTick=()=>{if(this._progress=xt(performance.now()-this._holdStart,wt),this._progress>=1){this._commit();return}this._raf=requestAnimationFrame(this._holdTick)};this._onHoldDown=e=>{this.disabled||(e.target.setPointerCapture?.(e.pointerId),this._arming=!0,this._holdStart=performance.now(),this._raf=requestAnimationFrame(this._holdTick))};this._onHoldUp=()=>{this._progress<1&&this._reset()};this._onSlideDown=e=>{if(this.disabled)return;let i=e.currentTarget.closest(".track");this._trackRect=i?.getBoundingClientRect()??null;let r=i?.querySelector(".knob");this._knobW=r?.getBoundingClientRect().width||Ve,e.target.setPointerCapture?.(e.pointerId),this._arming=!0};this._onSlideMove=e=>{!this._arming||!this._trackRect||(this._progress=bt(e.clientX,this._trackRect.left,this._trackRect.width,this._knobW))};this._onSlideUp=()=>{this._progress>=yt?this._commit():this._reset()};this._onTap=()=>{this.disabled||this._fireOpen()}}get _ariaLabel(){return this.label||m(this.uiLang).open.labelDefault}disconnectedCallback(){super.disconnectedCallback(),this._reset()}updated(e){e.has("status")&&(this.status==="idle"||this.status==="error")&&(this._progress=0)}_fireOpen(){this.dispatchEvent(new CustomEvent("open",{bubbles:!0,composed:!0}))}_reset(){this._raf&&cancelAnimationFrame(this._raf),this._raf=0,this._arming=!1,this._progress=0,this._trackRect=null}_commit(){this._raf&&cancelAnimationFrame(this._raf),this._raf=0,this._arming=!1,this._progress=1,this._trackRect=null,this._fireOpen()}render(){let e=this.mode==="tap"?this._renderTap():this.mode==="slide"?this._renderSlide():this._renderHold();return c`
      <div class="wrap" style="--eg-prog:${this._vp()}">
        ${e}
        ${this._caption()}
      </div>
    `}_caption(){let e=m(this.uiLang).open,i="",r="";return this.status==="opened"?(i=e.captionOpened,r="st-opened"):this.status==="error"?(i=e.captionError,r="st-error"):this.status==="opening"?i="":this.mode==="slide"&&(i=e.captionSlideHint),c`<span class="caption ${r}">${i||c`&nbsp;`}</span>`}_labelText(){let e=m(this.uiLang).open;return this.status==="opened"?e.opened:this.status==="opening"?e.opening:this.mode==="slide"?e.slide:e.hold}_barIcon(){return this.status==="opening"?"loader-circle":this.status==="opened"?"lock-open":"key-round"}_knobIcon(){return this.status==="opening"?"loader-circle":"key-round"}_vp(){return this.status==="opening"||this.status==="opened"?1:this._progress}_statusClass(){return this.status==="opened"?"st-opened":this.status==="opening"?"st-opening":this.status==="error"?"st-error":""}_renderTap(){return c`
      <button class="pill tap ${this._statusClass()}" ?disabled=${this.disabled} @click=${this._onTap}
              aria-label=${this._ariaLabel}>
        <div class="fill"></div>
        <span class="content"><eg-icon name=${this._barIcon()}></eg-icon>${this._labelText()}</span>
      </button>
    `}_renderHold(){return c`
      <button
        class="pill hold ${this._arming?"arming":""} ${this._statusClass()}"
        ?disabled=${this.disabled}
        aria-label="${this._ariaLabel} ${m(this.uiLang).open.holdAriaSuffix}"
        @pointerdown=${this._onHoldDown}
        @pointerup=${this._onHoldUp}
        @pointercancel=${this._onHoldUp}
        @pointerleave=${this._onHoldUp}
      >
        <div class="fill"></div>
        <span class="content"><eg-icon name=${this._barIcon()}></eg-icon>${this._labelText()}</span>
      </button>
    `}_renderSlide(){return c`
      <div
        class="track ${this._statusClass()} ${this._arming?"dragging":""}"
        role="slider"
        aria-label=${this._ariaLabel}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${Math.round(this._vp()*100)}
      >
        <eg-icon class="lock-under" name="lock"></eg-icon>
        <eg-icon class="end" name="lock-open"></eg-icon>
        <div class="fill"></div>
        <span class="label">${this._labelText()}</span>
        <div
          class="knob ${this.disabled?"off":""} ${this.status==="opening"?"loading":""}"
          @pointerdown=${this._onSlideDown}
          @pointermove=${this._onSlideMove}
          @pointerup=${this._onSlideUp}
          @pointercancel=${this._onSlideUp}
        >
          <eg-icon name=${this._knobIcon()}></eg-icon>
        </div>
      </div>
    `}};A.styles=[z,x`
      :host {
        display: block;
      }
      .wrap {
        display: flex;
        flex-direction: column;
        gap: calc(8px * var(--eg-scale, 1));
        align-items: center;
        width: 100%;
      }
      /* ---- общая заливка-прогресс ---- */
      .fill {
        position: absolute;
        inset: 0 auto 0 0;
        width: calc(var(--eg-prog, 0) * 100%);
        background: var(--eg-primary);
        opacity: 0.15;
        transition: width 0.2s ease;
      }
      /* ---- slide: трек 300×80 в масштабе 1 (макет: центрирован, не на всю
         ширину); при --eg-scale трек/ключ растут пропорционально, ширина не
         превышает контейнер (min(...,100%)) — на панели слайдер крупный ---- */
      .track {
        position: relative;
        width: min(calc(300px * var(--eg-scale, 1)), 100%);
        height: calc(80px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        touch-action: none;
        user-select: none;
      }
      /* в покое заливки нет (иначе «залипло»); появляется только при перетаскивании */
      .track .fill {
        width: 0;
      }
      /* при drag правый край заливки строго = центр ключа (не обгоняет) */
      .track.dragging .fill {
        width: calc(
          40px * var(--eg-scale, 1) + var(--eg-prog, 0) * (100% - 80px * var(--eg-scale, 1))
        );
        transition: none;
      }
      /* открытие (loading): доведено до конца — заливка на всю ширину + пульс */
      .track.st-opening .fill {
        width: 100%;
        background: var(--eg-primary);
        opacity: 0.15;
        animation: eg-pulse 1.1s ease-in-out infinite;
      }
      /* закрытый замок под ключом (проявляется при отъезде): иконка 20, центр под ключом */
      .lock-under {
        position: absolute;
        left: calc(30px * var(--eg-scale, 1));
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: calc(20px * var(--eg-scale, 1));
        color: var(--eg-text-3);
        z-index: 0;
      }
      /* торец: открытый замок (макет: иконка 20, центр 28px от правого края) */
      .end {
        position: absolute;
        right: calc(18px * var(--eg-scale, 1));
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: calc(20px * var(--eg-scale, 1));
        color: var(--eg-text-3);
        z-index: 0;
      }
      .track .label {
        position: relative;
        z-index: 1;
        font-size: calc(17px * var(--eg-scale, 1));
        font-weight: 600;
        color: var(--eg-text);
      }
      .knob {
        position: absolute;
        top: calc(6px * var(--eg-scale, 1));
        left: calc(6px * var(--eg-scale, 1) + var(--eg-prog, 0) * (100% - 80px * var(--eg-scale, 1)));
        width: calc(68px * var(--eg-scale, 1));
        height: calc(68px * var(--eg-scale, 1));
        border-radius: 50%;
        background: var(--eg-primary);
        color: var(--eg-on-fill);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        touch-action: none;
        z-index: 2;
        --eg-icon-size: calc(28px * var(--eg-scale, 1));
        transition: left 0.18s ease;
      }
      .track.dragging .knob {
        transition: none;
        cursor: grabbing;
      }
      .knob.off {
        opacity: 0.5;
      }
      /* slide success: зелёный трек + «Открыто» + ключ справа */
      .track.st-opened .fill {
        background: var(--eg-success);
        opacity: 1;
        width: 100%;
      }
      .track.st-opened .label {
        color: var(--eg-on-fill);
      }
      .track.st-opened .knob {
        background: var(--eg-success);
      }
      /* success: ключ-knob уехал вправо и накрыл торец — торец прячем */
      .track.st-opened .end {
        display: none;
      }
      /* ---- hold/tap: outlined-пилюля, контент неподвижен, заливка бежит ---- */
      .pill {
        position: relative;
        width: 100%;
        min-height: calc(64px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        border: 2px solid var(--eg-primary);
        background: transparent;
        color: var(--eg-text);
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        cursor: pointer;
        touch-action: none;
        user-select: none;
        font: inherit;
        padding: 0 calc(16px * var(--eg-scale, 1));
      }
      .pill.arming .fill {
        transition: none;
      }
      .pill .fill {
        opacity: 0.2;
      }
      .pill .content {
        position: relative;
        z-index: 1;
        display: inline-flex;
        align-items: center;
        gap: calc(8px * var(--eg-scale, 1));
        font-size: calc(17px * var(--eg-scale, 1));
        font-weight: 600;
        --eg-icon-size: calc(24px * var(--eg-scale, 1));
      }
      .pill[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .pill.st-opened {
        border-color: var(--eg-success);
      }
      .pill.st-opened .fill {
        background: var(--eg-success);
        opacity: 1;
        width: 100%;
      }
      .pill.st-opened .content {
        color: var(--eg-on-fill);
      }
      /* ---- подпись под контролом ---- */
      .caption {
        font-size: calc(12px * var(--eg-scale, 1));
        color: var(--eg-text-3);
        text-align: center;
      }
      .caption.st-opened {
        color: var(--eg-success);
      }
      .caption.st-error {
        color: var(--eg-error);
      }
      /* спиннер на ключе слайдера / иконке пилюли во время открытия */
      .knob.loading eg-icon,
      .pill.st-opening .content eg-icon {
        animation: eg-spin 0.8s linear infinite;
      }
      @keyframes eg-spin {
        to {
          transform: rotate(360deg);
        }
      }
      @keyframes eg-pulse {
        0%,
        100% {
          opacity: 0.12;
        }
        50% {
          opacity: 0.26;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .fill,
        .knob {
          transition: none;
        }
        .knob.loading eg-icon,
        .pill.st-opening .content eg-icon,
        .track.st-opening .fill {
          animation: none;
        }
      }
    `],o([u()],A.prototype,"mode",2),o([u({type:Boolean})],A.prototype,"disabled",2),o([u()],A.prototype,"label",2),o([u()],A.prototype,"uiLang",2),o([u()],A.prototype,"status",2),o([v()],A.prototype,"_progress",2),o([v()],A.prototype,"_arming",2),A=o([k("eg-open-control")],A);function We(s,t,e=!1){return!t||s==="denied"?!1:s==="granted"||e}function Ke(s,t,e){return s?t==="denied"?"denied":t==="prompt"&&!e?"prompt":"none":"no_https"}var F=class F{constructor(t,e=()=>{}){this._getConn=t;this._onChange=e;this.active=!1;this.lastError=""}hasGrantedBefore(){try{return typeof localStorage<"u"&&localStorage.getItem(F._GRANT_KEY)==="1"}catch{return!1}}markGranted(){try{typeof localStorage<"u"&&localStorage.setItem(F._GRANT_KEY,"1")}catch{}}async queryPermission(){try{return(await navigator.permissions?.query({name:"microphone"}))?.state??"unknown"}catch{return"unknown"}}get secure(){return typeof window<"u"&&window.isSecureContext===!0}async start(){if(this.active)return;let t=this._getConn();if(!t){this._fail("\u043D\u0435\u0442 \u0441\u0432\u044F\u0437\u0438 \u0441 Home Assistant");return}if(!navigator.mediaDevices?.getUserMedia){this._fail("\u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D (\u043D\u0443\u0436\u0435\u043D HTTPS-origin)");return}try{let e=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:!0,noiseSuppression:!0,autoGainControl:!0}}),i=window.AudioContext||window.webkitAudioContext,r=new i,n=r.sampleRate,a=this._sub;(!a||a.sampleRate!==n)&&(a={handlerId:(await t.sendMessagePromise({type:"elektronny_gorod/intercom_uplink",sample_rate:n})).handler_id,sampleRate:n},this._sub=a);let p=a.handlerId,d=t.socket;await r.audioWorklet.addModule(this._workletUrl());let g=new AudioWorkletNode(r,"eg-pcm-int16",{numberOfOutputs:0});g.port.onmessage=h=>{let w=h.data,$=new Uint8Array(1+w.byteLength);$[0]=p,$.set(new Uint8Array(w.buffer),1),d.readyState===1&&d.send($)};let f=r.createMediaStreamSource(e);f.connect(g),this._ctx={ac:r,stream:e,node:g,src:f},this.active=!0,this.lastError="",this.markGranted(),this._onChange()}catch(e){this._fail(e instanceof Error?e.message:String(e))}}stop(){let t=this._ctx;if(t){try{t.node.port.onmessage=null,t.node.disconnect(),t.src.disconnect()}catch{}try{t.stream.getTracks().forEach(e=>e.stop())}catch{}try{t.ac.close()}catch{}}if(this._ctx=void 0,this.active=!1,this._wUrl){try{URL.revokeObjectURL(this._wUrl)}catch{}this._wUrl=void 0}this._onChange()}_fail(t){this.lastError=t,this.stop()}_workletUrl(){if(this._wUrl)return this._wUrl;let t=`
      class EgPcmInt16 extends AudioWorkletProcessor {
        process(inputs) {
          const ch = inputs[0] && inputs[0][0];
          if (ch && ch.length) {
            const i16 = new Int16Array(ch.length);
            for (let i = 0; i < ch.length; i++) {
              const s = Math.max(-1, Math.min(1, ch[i]));
              i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
            }
            this.port.postMessage(i16, [i16.buffer]);
          }
          return true;
        }
      }
      registerProcessor("eg-pcm-int16", EgPcmInt16);`;return this._wUrl=URL.createObjectURL(new Blob([t],{type:"application/javascript"})),this._wUrl}};F._GRANT_KEY="eg-intercom-mic-granted";var se=F;var $t=new Set(["slide","hold","tap"]);function Ge(s,t){return s&&$t.has(s)?s:t?"slide":"hold"}function Fe(){return typeof window<"u"&&typeof window.matchMedia=="function"&&window.matchMedia("(pointer: coarse)").matches}var ne=new Set(["ringing","connecting","active","error"]),At=6e3,kt=3e3,Ye=3e4,St=2500,_=class extends b{constructor(){super(...arguments);this._config={};this._muted=!1;this._audioBlocked=!1;this._micActive=!1;this._micPerm="unknown";this._openStatus="idle";this._now=Date.now();this._ringingSince=0;this._errDismissed=new Set;this._endedEntity="";this._endedDuration="";this._doorbells=[];this._openAction="hold";this._prevKey="";this._prevPhases=new Map;this._mic=new se(()=>this.hass?.connection,()=>{this._micActive=this._mic.active,this.requestUpdate()});this._clearEnded=()=>{this._endedHide&&(clearTimeout(this._endedHide),this._endedHide=void 0),this._endedEntity="",this.requestUpdate()};this._unmute=()=>{this._muted=!1,this._audioBlocked=!1};this._answer=()=>{this.hass?.callService("elektronny_gorod","answer")};this._hangup=()=>{this.hass?.callService("elektronny_gorod","hangup")};this._toggleMute=()=>{this._muted=!this._muted};this._toggleMic=async()=>{this._mic.active?this._mic.stop():await this._mic.start(),this._micPerm=await this._mic.queryPermission()};this._open=async()=>{let e=this._active?.lock;if(!(!e||!this.hass)){this._openStatus="opening";try{await this.hass.callService("lock","unlock",{entity_id:e}),this._openStatus="opened"}catch{this._openStatus="error"}this._openReset&&clearTimeout(this._openReset),this._openReset=window.setTimeout(()=>{this._openStatus="idle",this.requestUpdate()},kt)}};this._dismiss=()=>{this.dispatchEvent(new CustomEvent("eg-dismiss",{bubbles:!0,composed:!0}))};this._retry=()=>{this.hass?.callService("elektronny_gorod","answer")}}setConfig(e){let i=e?.doorbells??(e?.call_state?[{call_state:e.call_state,doorbell_camera:e.doorbell_camera,lock:e.lock,name:e.name,address:e.address}]:[]);if(!i.length||i.some(r=>!r.call_state))throw new Error("eg-intercom-call-card: \u0443\u043A\u0430\u0436\u0438\u0442\u0435 'doorbells' (\u0441 call_state) \u0438\u043B\u0438 'call_state'");this._config=e,this._doorbells=i,this._openAction=Ge(e.open_action,Fe())}getCardSize(){return 8}static getStubConfig(){return{camera:"",doorbells:[{call_state:"",doorbell_camera:"",lock:""}]}}disconnectedCallback(){super.disconnectedCallback(),this._mic.stop(),this._stopTick(),this._errHide&&clearTimeout(this._errHide),this._openReset&&clearTimeout(this._openReset),this._endedHide&&clearTimeout(this._endedHide)}_phaseOf(e){let i=this.hass?.states[e.call_state]?.state;return Ue(i)}get _active(){let e=this._doorbells.find(i=>ne.has(this._phaseOf(i))&&!this._errDismissed.has(i.call_state));if(e)return e;if(this._endedEntity)return this._doorbells.find(i=>i.call_state===this._endedEntity)}get _phase(){let e=this._active;if(!e)return"idle";let i=this._phaseOf(e);return ne.has(i)?i:e.call_state===this._endedEntity?"ended":"idle"}get _intercomName(){let e=this._active;if(e?.name)return e.name;let r=(e?this.hass?.states[e.call_state]?.attributes:void 0)?.intercom_name;return(typeof r=="string"?r.replace(/\s+/g," ").trim():"")||this._config.name||m(this._lang).nameFallback}get _address(){return this._active?.address??this._config.address??""}get _lang(){return ze(this.hass)}get _startedAtMs(){let e=this._active,i=e?this.hass?.states[e.call_state]?.attributes?.started_at:void 0;if(typeof i!="string")return;let r=Date.parse(i);return Number.isNaN(r)?void 0:r}willUpdate(e){if(!e.has("hass"))return;for(let n of this._doorbells){let a=this._phaseOf(n),p=this._prevPhases.get(n.call_state);this._prevPhases.set(n.call_state,a),this._errDismissed.has(n.call_state)&&a!=="error"&&this._errDismissed.delete(n.call_state),a==="ended"&&p!==void 0&&ne.has(p)&&p!=="error"&&this._enterEnded(n),this._endedEntity===n.call_state&&ne.has(a)&&this._clearEnded()}let i=this._active,r=i?`${i.call_state}|${this._phase}`:"idle";r!==this._prevKey&&(this._onPhase(this._phase,i),this._prevKey=r)}_enterEnded(e){this._endedDuration=this._durationOf(e),this._endedEntity=e.call_state,this._endedHide&&clearTimeout(this._endedHide),this._endedHide=window.setTimeout(()=>this._clearEnded(),St)}_durationOf(e){let i=this.hass?.states[e.call_state]?.attributes?.started_at;if(typeof i!="string")return"";let r=Date.parse(i);return Number.isNaN(r)?"":this._mmss(Math.max(0,Math.floor((Date.now()-r)/1e3)))}_onPhase(e,i){e==="active"?this._enterActive():e==="ringing"?(this._ringingSince=Date.now(),this._startTick()):this._exitActive(),e==="error"&&i&&this._scheduleErrDismiss(i.call_state),(e==="idle"||e==="ringing")&&(this._openStatus="idle")}async _enterActive(){if(this._muted=!1,this._audioBlocked=this._detectAudioBlocked(),this._startTick(),this._config.mic===!1||(this._micPerm=await this._mic.queryPermission(),this._phase!=="active"))return;this._config.mic_autostart!==!1&&We(this._micPerm,this._mic.secure,this._mic.hasGrantedBefore())&&(await this._mic.start(),this._micPerm=await this._mic.queryPermission())}_detectAudioBlocked(){let e=navigator.userActivation;return e?!e.hasBeenActive:!1}_exitActive(){this._mic.stop(),this._stopTick(),this._audioBlocked=!1}_startTick(){this._stopTick(),this._now=Date.now(),this._tick=window.setInterval(()=>{this._now=Date.now()},1e3)}_stopTick(){this._tick&&(clearInterval(this._tick),this._tick=void 0)}_scheduleErrDismiss(e){this._errHide&&clearTimeout(this._errHide),this._errHide=window.setTimeout(()=>{this._errDismissed=new Set(this._errDismissed).add(e),this.requestUpdate()},At)}_timerText(){let e=this._startedAtMs;if(e===void 0)return"";let i=Math.max(0,Math.floor((this._now-e)/1e3));return this._mmss(i)}_mmss(e){let i=String(Math.floor(e/60)).padStart(2,"0"),r=String(e%60).padStart(2,"0");return`${i}:${r}`}_answerWindow(){if(!this._ringingSince)return{text:"",fraction:0};let e=Math.max(0,Ye-(this._now-this._ringingSince)),i=Math.ceil(e/1e3);return{text:`${Math.floor(i/60)}:${String(i%60).padStart(2,"0")}`,fraction:e/Ye}}_stageState(e,i,r){if(r==="ended")return"ended";if(e.isError)return"connection_lost";let n=i?this.hass?.states[i]:void 0;return!n||n.state==="unavailable"?"camera_off":"live"}get _micBanner(){return this._config.mic===!1||this._phase!=="active"||this._micActive?"none":Ke(this._mic.secure,this._micPerm,this._mic.hasGrantedBefore())}get _micBlocked(){return!this._mic.secure||this._micPerm==="denied"}render(){let e=this._active;if(!e)return this._renderIdle();let i=this._phase,r=Ne(i),n=qe(r.video,{camera:this._config.camera,doorbell_camera:e.doorbell_camera});if(this._config.layout==="compact")return this._renderCompact(e,i,r,n);let a=this._stageState(r,n,i);return c`
      <ha-card class="phase-${i}">
        <div class="content">
          ${this._renderHeader()}
          ${this._renderStatus(r,i)}
          <div class="stage">
            <eg-call-stage
              .hass=${this.hass}
              .uiLang=${this._lang}
              .entity=${n}
              .muted=${this._muted||this._audioBlocked}
              .live=${a==="live"}
              .soundOff=${i==="active"&&this._muted&&!this._audioBlocked}
              .stageState=${a}
              .audioBlocked=${this._audioBlocked}
              @unmute=${this._unmute}
            ></eg-call-stage>
          </div>
          <div class="controls">
            ${(()=>{let p=this._micBanner;return p!=="none"?this._renderMicBanner(p):l})()}
            <div class="open-area">
              ${r.showOpen?this._renderOpen():l}
            </div>
            ${this._renderActions(r)}
          </div>
        </div>
      </ha-card>
    `}_renderHeader(){let e=this._address;return c`
      <header>
        <div class="hgroup">
          <span class="name" title=${this._intercomName}>${this._intercomName}</span>
          ${e?c`<span class="addr">${e}</span>`:l}
        </div>
        <button class="close" @click=${this._dismiss} aria-label=${m(this._lang).minimize}>
          <eg-icon name="x"></eg-icon>
        </button>
      </header>
    `}_renderStatus(e,i){let r=e.showTimer&&this._config.timer!=="off",n=e.showAnswerWindow?this._answerWindow():null;return c`
      <div class="statusrow">
        <div class="strow">
          <span class="badge" style="--badge:${_e(i)}">
            <span class="dot" aria-hidden="true"></span>
            <span>${m(this._lang).status[i]??""}</span>
          </span>
          ${n?c`<span class="countdown"><eg-icon name="timer"></eg-icon>${n.text}</span>`:r?c`<span class="timer">${this._timerText()}</span>`:i==="ended"&&this._endedDuration?c`<span class="timer ended-dur">${this._endedDuration}</span>`:l}
        </div>
        ${n?c`<div class="window"><div class="fill" style="width:${n.fraction*100}%"></div></div>`:l}
      </div>
    `}_doorbellNames(){return this._doorbells.map(e=>{let i=this.hass?.states[e.call_state]?.attributes?.intercom_name;return e.name??(typeof i=="string"?i:"")}).filter(Boolean)}_renderIdle(){let e=this._doorbellNames();return c`
      <ha-card class="idle">
        <div class="idle-box" role="status">
          <div class="idle-ico"><eg-icon name="door-closed"></eg-icon></div>
          <div class="idle-title">${this._config.idle_text??m(this._lang).idle.title}</div>
          <div class="idle-sub">${m(this._lang).idle.sub}</div>
          ${e.length?c`<div class="idle-chips">
                ${e.map(i=>c`<span class="chip"><eg-icon name="door-open"></eg-icon>${i}</span>`)}
              </div>`:l}
        </div>
      </ha-card>
    `}_renderCompact(e,i,r,n){let a=this._stageState(r,n,i);return c`
      <ha-card class="compact phase-${i}">
        <div class="cx-thumb">
          ${n?c`<eg-call-video .hass=${this.hass} .entity=${n} .muted=${!0}></eg-call-video>`:l}
          ${a==="live"?c`<span class="cx-live">LIVE</span>`:l}
        </div>
        <div class="cx-info">
          <span class="cx-name" title=${this._intercomName}>${this._intercomName}</span>
          <span class="cx-status" style="--badge:${_e(i)}">
            <span class="cx-dot" aria-hidden="true"></span>
            <span>${this._compactStatus(i)}</span>
          </span>
        </div>
        <div class="cx-btns">
          ${r.showOpen&&e.lock?this._quickBtn("key-round",m(this._lang).open.slide,this._open,"q-open"):l}
          ${r.actions.map(p=>this._quickAction(p))}
        </div>
      </ha-card>
    `}_quickAction(e){let i=m(this._lang).action;switch(e){case"accept":return this._quickBtn("phone",i.accept,this._answer,"q-accept");case"reject":case"cancel":case"hangup":return this._quickBtn("phone-off",i.hangup,this._hangup,"q-reject");case"close":return this._quickBtn("x",i.close,this._clearEnded,"");default:return l}}_quickBtn(e,i,r,n){return c`
      <button class="q-btn ${n}" @click=${r} aria-label=${i}>
        <eg-icon name=${e}></eg-icon>
      </button>
    `}_compactStatus(e){let i=m(this._lang).compact;return e==="ringing"?`${i.call} \xB7 ${this._answerWindow().text}`:e==="active"?`${i.talk} \xB7 ${this._timerText()}`:e==="connecting"?i.connecting:e==="ended"?this._endedDuration?`${i.ended} \xB7 ${this._endedDuration}`:i.ended:e==="error"?i.error:""}_renderMicBanner(e){let i=m(this._lang).micBanner[e];return c`
      <div class="mic-banner" role="alert">
        <eg-icon name="mic-off"></eg-icon>
        <div class="mb-text">
          <span class="mb-title">${i.title}</span>
          <span class="mb-sub">${i.sub}</span>
        </div>
        ${i.cta?c`<button class="mb-btn" @click=${this._toggleMic}>${i.cta}</button>`:l}
      </div>
    `}_renderOpen(){return c`
      <eg-open-control
        .mode=${this._openAction}
        .status=${this._openStatus}
        .uiLang=${this._lang}
        ?disabled=${!this._active?.lock}
        @open=${this._open}
      ></eg-open-control>
    `}_circle(e,i,r,n=""){return c`
      <button class="circle ${n}" @click=${r} aria-label=${i}>
        <span class="ic"><eg-icon name=${e}></eg-icon></span>
        <small>${i}</small>
      </button>
    `}_renderActions(e){return c`<div class="actions">${e.actions.map(i=>this._renderAction(i))}</div>`}_renderAction(e){let i=m(this._lang).action;switch(e){case"accept":return this._circle("phone",i.accept,this._answer,"accept");case"reject":return this._circle("phone-off",i.reject,this._hangup,"reject");case"cancel":return this._circle("phone-off",i.cancel,this._hangup,"reject");case"connecting":return this._spinnerBtn(i.connecting);case"mic":return this._config.mic===!1?l:this._renderMic();case"sound":return this._audioBlocked?this._circle("volume-x",i.soundOff,this._unmute,"warn"):this._circle(this._muted?"volume-x":"volume-2",i.sound,this._toggleMute);case"hangup":return this._circle("phone-off",i.hangup,this._hangup,"reject");case"retry":return this._circle("refresh-cw",i.retry,this._retry,"retry");case"close":return this._circle("x",i.close,this._clearEnded);default:return l}}_spinnerBtn(e){return c`
      <div class="circle spinner-btn" role="status" aria-label=${e} aria-busy="true">
        <span class="ic"><eg-icon class="spin" name="loader-circle"></eg-icon></span>
        <small>${e}</small>
      </div>
    `}_renderMic(){let e=m(this._lang).action;if(this._micBlocked)return this._circle("mic-off",e.micNoAccess,this._toggleMic,"mic-blocked");let i=this._micActive?"mic":"mic-off",r=this._micActive?e.micOff:e.micOn;return c`<button class="circle" @click=${this._toggleMic} aria-label=${r}>
      <span class="ic"><eg-icon name=${i}></eg-icon></span><small>${e.mic}</small>
    </button>`}};_.styles=[z,x`
      :host {
        display: block;
        height: 100%;
        /* адаптив по собственной ширине карточки (телефон / планшет / десктоп / панель) */
        container-type: inline-size;
      }
      ha-card {
        height: 100%;
        box-sizing: border-box;
        background: var(--eg-card);
        border-radius: var(--eg-r-card);
      }
      .content {
        display: flex;
        flex-direction: column;
        gap: 20px;
        /* заполняем высоту карточки; вертикальный экран → верт. отступы вдвое больше
           горизонтальных (16), с учётом safe-area панели/телефона */
        min-height: 100%;
        padding: max(32px, env(safe-area-inset-top)) 16px max(32px, env(safe-area-inset-bottom));
        box-sizing: border-box;
      }
      /* Адаптивный масштаб контента: телефон = 1, на большом экране крупнее
         (настенная панель/десктоп — «читаемо с ~1м», UX §10). Наследуется в
         дочерние компоненты (open-control) через --eg-scale. */
      .content,
      ha-card.idle {
        --eg-scale: 1;
      }
      @container (min-width: 700px) {
        .content,
        ha-card.idle {
          --eg-scale: 1.35;
        }
      }
      @container (min-width: 1100px) {
        .content,
        ha-card.idle {
          --eg-scale: 1.7;
        }
      }
      @container (min-width: 1600px) {
        .content,
        ha-card.idle {
          --eg-scale: 2;
        }
      }
      /* шапка/статус/видео — сверху, фиксированной высоты */
      header,
      .statusrow,
      .stage {
        flex: none;
      }
      /* зона контролов заполняет остаток: слайдер по центру, кнопки — по нижней кромке */
      .controls {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      .controls .open-area {
        flex: 1;
        align-items: center;
      }
      .controls .actions {
        margin-top: auto;
      }
      /* ---- широкий контейнер (планшет / настенная панель / десктоп): 2 колонки.
         Порог 760px: видео + контролы РЯДОМ вертикально компактнее вертикального
         стека, поэтому на невысоких экранах ничего не переполняется (у стека
         video 16:9 + баннер + слайдер + кнопки не влезают по высоте). */
      @container (min-width: 760px) {
        .content {
          display: grid;
          /* Узкая колонка контролов фикс. ширины → видео (1fr) получает
             максимум ширины, а значит и высоты (оно всегда 16:9). Кнопки/
             слайдер — базового размера (.controls сбрасывает --eg-scale в 1):
             на десктопе (мышь, близко) укрупнённые touch-таргеты не нужны. */
          grid-template-columns: 1fr 320px;
          grid-template-areas:
            "header header"
            "status status"
            "stage controls";
          column-gap: 28px;
          row-gap: 20px;
          align-items: start;
          /* grid default align-content = stretch → строки растягивались (дыры);
             start = контент сверху, строка stage/controls по высоте видео */
          align-content: start;
          padding: 24px;
        }
        header {
          grid-area: header;
        }
        .statusrow {
          grid-area: status;
        }
        .stage {
          grid-area: stage;
          align-self: start;
        }
        /* Колонка контролов = высоте видео (align-self: stretch). Flex-поток
           (из базового .controls): баннер сверху, слайдер по центру свободного
           места, кнопки по нижней кромке — без наложения при любой высоте видео
           (в т.ч. на узком 760–900, где видео невысокое). */
        .controls {
          grid-area: controls;
          align-self: stretch;
          /* Базовый размер контролов на широком экране: --eg-scale укрупняет
             текст/оверлеи для читаемости, но кнопки/слайдер от него раздувались
             до ~2× («как для слепых» на десктопе). Здесь сбрасываем в 1. */
          --eg-scale: 1;
        }
      }
      /* ≥900px: видео уже выше стека контролов → абсолютное позиционирование,
         слайдер строго по ЦЕНТРУ видео, кнопки по нижней кромке, баннер сверху.
         На 760–900 остаётся flex-поток (выше) — иначе слайдер/кнопки налезали
         бы друг на друга на невысоком видео. */
      @container (min-width: 900px) {
        .controls {
          position: relative;
          display: block;
        }
        .controls .mic-banner {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
        }
        .controls .open-area {
          position: absolute;
          top: 50%;
          left: 0;
          right: 0;
          transform: translateY(-50%);
        }
        .controls .actions {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
        }
      }
      /* ---- шапка: имя + адрес + свернуть ---- */
      header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }
      .hgroup {
        display: flex;
        flex-direction: column;
        gap: 3px;
        min-width: 0;
      }
      .name {
        font-size: calc(22px * var(--eg-scale, 1));
        font-weight: 700;
        line-height: 1.15;
        color: var(--eg-text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .addr {
        font-size: calc(13px * var(--eg-scale, 1));
        color: var(--eg-text-2);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .close {
        flex: none;
        width: calc(44px * var(--eg-scale, 1));
        height: calc(44px * var(--eg-scale, 1));
        border: none;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        color: var(--eg-text-2);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
      }
      .close eg-icon {
        --eg-icon-size: calc(20px * var(--eg-scale, 1));
      }
      /* ---- статус-строка: бейдж + таймер/countdown + окно ответа ---- */
      .statusrow {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .strow {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: calc(7px * var(--eg-scale, 1));
        padding: calc(5px * var(--eg-scale, 1)) calc(12px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        font-size: calc(13px * var(--eg-scale, 1));
        font-weight: 600;
        color: var(--badge, var(--eg-text-2));
        background: color-mix(in srgb, var(--badge, var(--eg-text-2)) 18%, transparent);
      }
      .badge .dot {
        width: calc(8px * var(--eg-scale, 1));
        height: calc(8px * var(--eg-scale, 1));
        border-radius: 50%;
        background: var(--badge, var(--eg-text-2));
      }
      .countdown {
        display: inline-flex;
        align-items: center;
        gap: calc(6px * var(--eg-scale, 1));
        font-size: calc(15px * var(--eg-scale, 1));
        color: var(--eg-text-2);
      }
      .countdown eg-icon {
        --eg-icon-size: calc(15px * var(--eg-scale, 1));
      }
      .timer {
        font-family: var(--eg-mono);
        font-size: calc(17px * var(--eg-scale, 1));
        font-weight: 600;
        color: var(--eg-text);
        font-variant-numeric: tabular-nums;
      }
      .timer.ended-dur {
        color: var(--eg-text-3);
        font-weight: 500;
      }
      .window {
        width: 100%;
        height: 4px;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        overflow: hidden;
      }
      .window .fill {
        height: 100%;
        border-radius: var(--eg-r-full);
        background: var(--eg-warning);
        transition: width 1s linear;
      }
      /* ---- баннер «нет доступа к микрофону» ---- */
      .mic-banner {
        display: flex;
        align-items: center;
        gap: calc(12px * var(--eg-scale, 1));
        padding: calc(12px * var(--eg-scale, 1));
        border-radius: var(--eg-r-md);
        background: var(--eg-warning-bg);
      }
      .mic-banner > eg-icon {
        --eg-icon-size: calc(20px * var(--eg-scale, 1));
        color: var(--eg-warning);
      }
      .mb-text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        flex: 1;
        min-width: 0;
      }
      .mb-title {
        font-size: calc(13px * var(--eg-scale, 1));
        font-weight: 600;
        color: var(--eg-warning);
      }
      .mb-sub {
        font-size: calc(12px * var(--eg-scale, 1));
        color: var(--eg-text-2);
      }
      .mb-btn {
        flex: none;
        border: 1px solid var(--eg-warning);
        background: transparent;
        color: var(--eg-warning);
        font: inherit;
        font-size: calc(13px * var(--eg-scale, 1));
        font-weight: 600;
        border-radius: var(--eg-r-full);
        padding: calc(6px * var(--eg-scale, 1)) calc(14px * var(--eg-scale, 1));
        cursor: pointer;
      }
      /* ---- видео-стейдж ---- */
      .stage {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        border-radius: var(--eg-r-md);
        overflow: hidden;
        background: var(--eg-elevated);
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .spin {
          animation: none;
        }
      }
      /* ---- зона «Открыть» ---- */
      .open-area {
        display: flex;
        justify-content: center;
      }
      .open-area eg-open-control {
        width: 100%;
      }
      /* ---- ряд действий: круги top-align (как в макете), gap 28 ---- */
      .actions {
        display: flex;
        gap: calc(28px * var(--eg-scale, 1));
        justify-content: center;
        align-items: flex-start;
        flex-wrap: wrap;
      }
      .circle {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: calc(8px * var(--eg-scale, 1));
        border: none;
        background: none;
        cursor: pointer;
        color: var(--eg-text);
        font: inherit;
        padding: 0;
      }
      .circle .ic {
        width: calc(68px * var(--eg-scale, 1));
        height: calc(68px * var(--eg-scale, 1));
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-elevated);
        color: var(--eg-text);
      }
      .circle .ic eg-icon {
        --eg-icon-size: calc(28px * var(--eg-scale, 1));
      }
      .circle small {
        font-size: calc(12px * var(--eg-scale, 1));
        font-weight: 500;
        color: var(--eg-text-2);
      }
      .circle[disabled] {
        cursor: not-allowed;
        opacity: 0.5;
      }
      /* Все кнопки ряда — единый стиль: круг 68, иконка 28, подпись fs12/fw500/text-2.
         Акцент действия — только ЦВЕТОМ круга (см. call-card-ux-production.md §6/§9). */
      .circle.accept .ic {
        background: var(--eg-success);
        color: var(--eg-on-fill);
      }
      .circle.reject .ic {
        background: var(--eg-error);
        color: var(--eg-on-fill);
      }
      .circle.retry .ic {
        background: var(--eg-primary);
        color: var(--eg-on-fill);
      }
      /* audio_blocked: «Звук выкл.» — warning-иконка на elevated */
      .circle.warn .ic {
        color: var(--eg-warning);
      }
      .circle.warn small {
        color: var(--eg-warning);
      }
      /* микрофон недоступен: красный индикатор «Нет доступа» (iUNo1) */
      .circle.mic-blocked .ic {
        background: var(--eg-error-bg);
        color: var(--eg-error);
      }
      .circle.mic-blocked small {
        color: var(--eg-error);
      }
      /* «Соединяем…» — неинтерактивно, приглушённый крутящийся loader */
      .spinner-btn {
        cursor: default;
      }
      .spinner-btn small {
        color: var(--eg-text-3);
      }
      .spinner-btn .ic eg-icon.spin {
        color: var(--eg-text-2);
        animation: spin 0.9s linear infinite;
      }
      /* ---- idle-заглушка (узел aSs3Z) ---- */
      ha-card.idle {
        height: 100%;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 18px;
      }
      .idle-box {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: calc(18px * var(--eg-scale, 1));
        text-align: center;
      }
      .idle-ico {
        width: calc(76px * var(--eg-scale, 1));
        height: calc(76px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .idle-ico eg-icon {
        --eg-icon-size: calc(36px * var(--eg-scale, 1));
        color: var(--eg-text-3);
      }
      .idle-title {
        font-size: calc(22px * var(--eg-scale, 1));
        font-weight: 700;
        color: var(--eg-text);
      }
      .idle-sub {
        font-size: calc(15px * var(--eg-scale, 1));
        color: var(--eg-text-2);
        max-width: 40ch;
      }
      .idle-chips {
        display: flex;
        flex-wrap: wrap;
        gap: calc(10px * var(--eg-scale, 1));
        justify-content: center;
        padding-top: calc(6px * var(--eg-scale, 1));
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: calc(7px * var(--eg-scale, 1));
        padding: calc(9px * var(--eg-scale, 1)) calc(16px * var(--eg-scale, 1));
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        color: var(--eg-text-2);
        font-size: calc(14px * var(--eg-scale, 1));
        font-weight: 500;
      }
      .chip eg-icon {
        --eg-icon-size: calc(16px * var(--eg-scale, 1));
        color: var(--eg-text-2);
      }
      /* ---- компактная строка (layout: compact) — узел aSs3Z ---- */
      ha-card.compact {
        height: auto;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        box-sizing: border-box;
      }
      .cx-thumb {
        position: relative;
        width: 80px;
        height: 60px;
        flex: none;
        border-radius: 10px;
        overflow: hidden;
        background: #20262b;
      }
      .cx-thumb eg-call-video {
        position: absolute;
        inset: 0;
      }
      .cx-live {
        position: absolute;
        top: 6px;
        left: 6px;
        padding: 2px 6px;
        border-radius: var(--eg-r-full);
        background: rgba(211, 47, 47, 0.88);
        color: #fff;
        font-size: 8px;
        font-weight: 700;
        letter-spacing: 0.04em;
      }
      .cx-info {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .cx-name {
        font-size: 15px;
        font-weight: 700;
        color: var(--eg-text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .cx-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 500;
        color: var(--badge, var(--eg-text-2));
      }
      .cx-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--badge, var(--eg-text-2));
        flex: none;
      }
      .cx-btns {
        display: flex;
        gap: 8px;
        flex: none;
      }
      .q-btn {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-elevated);
        color: var(--eg-text);
      }
      .q-btn eg-icon {
        --eg-icon-size: 20px;
      }
      .q-btn.q-open {
        background: var(--eg-primary);
        color: var(--eg-on-fill);
      }
      .q-btn.q-accept {
        background: var(--eg-success);
        color: var(--eg-on-fill);
      }
      .q-btn.q-reject {
        background: var(--eg-error);
        color: var(--eg-on-fill);
      }
    `],o([u({attribute:!1})],_.prototype,"hass",2),o([v()],_.prototype,"_config",2),o([v()],_.prototype,"_muted",2),o([v()],_.prototype,"_audioBlocked",2),o([v()],_.prototype,"_micActive",2),o([v()],_.prototype,"_micPerm",2),o([v()],_.prototype,"_openStatus",2),o([v()],_.prototype,"_now",2),o([v()],_.prototype,"_ringingSince",2),o([v()],_.prototype,"_errDismissed",2),o([v()],_.prototype,"_endedEntity",2),o([v()],_.prototype,"_endedDuration",2),_=o([k("eg-intercom-call-card")],_);window.customCards=window.customCards||[];window.customCards.push({type:"eg-intercom-call-card",name:"EG Intercom \u2014 Call screen / \u042D\u0413 \u0414\u043E\u043C\u043E\u0444\u043E\u043D \u2014 \u042D\u043A\u0440\u0430\u043D \u0432\u044B\u0437\u043E\u0432\u0430",description:"Doorbell incoming call & talk: video+audio, open door, accept/hang up, mic \u2014 one card for all intercoms. \u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432 \u0438 \u0440\u0430\u0437\u0433\u043E\u0432\u043E\u0440 \u0441 \u0434\u043E\u043C\u043E\u0444\u043E\u043D\u043E\u043C: \u0432\u0438\u0434\u0435\u043E+\u0437\u0432\u0443\u043A, \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C, \u043F\u0440\u0438\u043D\u044F\u0442\u044C/\u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C, \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D.",preview:!1});export{_ as EgIntercomCallCard};
