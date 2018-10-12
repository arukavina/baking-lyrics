import React from "react";
import { Button, Grid, Row, Col } from "react-bootstrap";


const Lyrics = ({ lyrics, artist, title }) => (
    <div className='lyrics'>
      <h1><span>{title}</span></h1>
      <div>
        <pre>
          { lyrics }
        </pre>
        <p>{ artist} </p>
      </div>
    </div>);

export default class Hello extends React.Component {
    constructor(props) {
        super(props);
      this.state = {
        greeting: 'Try it now!',
        lyrics: '',
        artist: '',
      };

        // This binding is necessary to make `this` work in the callback
        this.getPythonHello = this.getPythonHello.bind(this);
    }

    personaliseGreeting({ title, lyrics, artist }) {
      this.setState({
        lyrics,
        title,
        artist: artist[0].name,
      });
    }

    getPythonHello() {
      fetch('/api/v1/general/random')
        .then(res => res.json())
        .then(data => this.personaliseGreeting(data));
    }

    render () {
        return (
          <div className={!this.state.lyrics ? "center" : 'up'}>
                <div>
                    <h1>{this.state.greeting}</h1>
                    <div className="wrapper">
                      <div className="item1">
                        <Button bsSize="large" bsStyle="danger" onClick={this.getPythonHello}>
                        Get some Lyrics
                      </Button>
                      </div>
                    </div>
                 </div>
                <Lyrics lyrics={this.state.lyrics} artist={this.state.artist} title={this.state.title}/>
          </div>
        );
    }
}
